"""验证 rhino-control 的路由、引擎、输出保护、离线文档与协议失败边界。

使用装有官方 mcp 2.x 的外部 Python 运行；几何验收另在 Rhino 进程内执行。
"""
import asyncio
import io
import json
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import docs
import rhino
import mcp_client


def fake_app(path, version='8.30'):
    """创建不会启动的安装夹具，供版本与目录搜索边界检查。"""
    (path / 'Contents/MacOS').mkdir(parents=True)
    with (path / 'Contents/Info.plist').open('wb') as stream:
        plistlib.dump({'CFBundleIdentifier': 'com.mcneel.rhinoceros',
                      'CFBundleExecutable': 'Rhinoceros',
                      'CFBundleShortVersionString': version,
                      'CFBundleVersion': version + '.test'}, stream)
    executable = path / 'Contents/MacOS/Rhinoceros'
    executable.write_bytes(b'fixture; never execute')
    executable.chmod(0o755)
    return executable


class RuntimeBoundaries(unittest.TestCase):
    def test_generated_metadata_on_old_and_new_rhino_surfaces(self):
        # 模拟缺少新属性的旧版接口，覆盖 Rhino 8 实测无法发现的 Rhino 5 属性缺失。
        for major, sr, build, serial_name, engine in [
            (5, 0, None, 'DocumentId', 'ironpython'), (5, 12, '5.12.test', 'DocumentId', 'ironpython'),
            (6, 0, '6.0.test', 'RuntimeSerialNumber', 'ironpython'),
            (7, 0, '7.0.test', 'RuntimeSerialNumber', 'ironpython'),
            (8, 0, '8.0.test', 'RuntimeSerialNumber', 'ironpython'),
            (8, 0, '8.0.test', 'RuntimeSerialNumber', 'cpython'),
            (8, 30, '8.30.test', 'RuntimeSerialNumber', 'ironpython'),
            (8, 30, '8.30.test', 'RuntimeSerialNumber', 'cpython'),
        ]:
            app = SimpleNamespace(**({'Version': build} if build else {}))
            modules = {'Rhino': SimpleNamespace(RhinoApp=app),
                       'scriptcontext': SimpleNamespace(doc=SimpleNamespace(**{serial_name: 17})),
                       'rhinoscriptsyntax': SimpleNamespace(
                           ExeVersion=lambda: major, ExeServiceRelease=lambda: sr,
                           AllObjects=lambda: [], UnitSystem=lambda: 2,
                           UnitAbsoluteTolerance=lambda: 0.001),
                       'runtime_compat': None}  # 禁止从包导入，验证生成文件的自包含性。
            for kind in ('probe', 'smoke20'):
                with self.subTest(major=major, sr=sr, kind=kind), \
                        tempfile.TemporaryDirectory(prefix='rhino 测试 ') as temp, \
                        patch.dict(sys.modules, modules), \
                        patch('platform.python_implementation', return_value='CPython' if engine == 'cpython' else 'IronPython'):
                    script, output = Path(temp) / '单次.py', Path(temp) / '结果.json'
                    rhino.prepare(kind, script, output, major, engine)
                    source = script.read_text()
                    if kind == 'smoke20':
                        # 此处只验元数据；几何夹具必须在原生 Rhino 内执行。
                        source = source.rsplit('\nrun(', 1)[0]
                    namespace = {}
                    exec(compile(source, str(script), 'exec'), namespace)
                    value = json.loads(output.read_text()) if kind == 'probe' else namespace['runtime_info']()
                    self.assertEqual(value['rhino_major'], major)
                    self.assertEqual(value['rhino_service_release'], sr)
                    self.assertEqual(value['rhino_build'], build)
                    self.assertEqual(value['document_serial'], 17)
                    self.assertEqual(value['document_serial_source'], serial_name)

    def test_engine_selection_rejects_old_cpython_before_creating_files(self):
        with tempfile.TemporaryDirectory() as temp:
            script, output = Path(temp) / 'script.py', Path(temp) / 'result.json'
            with self.assertRaises(ValueError):
                rhino.prepare('probe', script, output, 7, 'cpython')
            self.assertFalse(script.exists())
            self.assertFalse(output.exists())
            result = rhino.prepare('probe', script, output, 8, 'cpython')
            self.assertEqual(result['engine'], 'cpython')
            self.assertTrue(result['macro'].startswith('_-ScriptEditor _Run '))
            self.assertEqual(script.read_text().splitlines()[0], '#! python 3')

    def test_probe_and_smoke_reject_wrong_engine_before_run(self):
        for kind in ('probe', 'smoke20'):
            for target_engine, actual_engine in [('cpython', 'IronPython'), ('ironpython', 'CPython')]:
                with self.subTest(kind=kind, target_engine=target_engine), tempfile.TemporaryDirectory() as temp:
                    called = []
                    modules = {
                        'Rhino': SimpleNamespace(
                            RhinoApp=SimpleNamespace(Version='8.30.test'),
                            DocObjects=SimpleNamespace(ObjectEnumeratorSettings=lambda: SimpleNamespace())),
                        'scriptcontext': SimpleNamespace(doc=SimpleNamespace(
                            RuntimeSerialNumber=1,
                            Objects=SimpleNamespace(GetObjectList=lambda settings: called.append('smoke_document')))),
                        'rhinoscriptsyntax': SimpleNamespace(
                            ExeVersion=lambda: 8, ExeServiceRelease=lambda: 30,
                            AllObjects=lambda: called.append('probe_document')),
                        'runtime_compat': None,
                    }
                    script, output = Path(temp) / 'script.py', Path(temp) / 'result'
                    rhino.prepare(kind, script, output, 8, target_engine)
                    with patch.dict(sys.modules, modules), \
                            patch('platform.python_implementation', return_value=actual_engine), \
                            self.assertRaisesRegex(RuntimeError, 'Wrong Python engine'):
                        exec(compile(script.read_text(), str(script), 'exec'), {})
                    self.assertEqual(called, [])
                    self.assertFalse(output.exists())

    def test_cross_major_compatibility_target_preserves_actual_runtime_evidence(self):
        # 旧目标在新版运行是受支持的兼容测试，不能伪造为旧版本体实测。
        for target in (5, 6, 7):
            for kind in ('probe', 'smoke20'):
                with self.subTest(target=target, kind=kind), tempfile.TemporaryDirectory() as temp:
                    stopped = []

                    def stop_before_geometry():
                        # run 已保存初始报告；在单位 setter 和 CASES 之前停止，绝不模拟几何通过。
                        stopped.append('before_geometry')
                        raise RuntimeError('intentional stop before geometry')

                    modules = {
                        'Rhino': SimpleNamespace(
                            RhinoApp=SimpleNamespace(Version='8.30.test'),
                            DocObjects=SimpleNamespace(ObjectEnumeratorSettings=lambda: SimpleNamespace())),
                        'scriptcontext': SimpleNamespace(doc=SimpleNamespace(
                            RuntimeSerialNumber=17,
                            Objects=SimpleNamespace(GetObjectList=lambda settings: []))),
                        'rhinoscriptsyntax': SimpleNamespace(
                            ExeVersion=lambda: 8, ExeServiceRelease=lambda: 30,
                            AllObjects=lambda: [], UnitSystem=lambda: 2,
                            UnitAbsoluteTolerance=lambda: 0.001, CurrentLayer=stop_before_geometry),
                        'runtime_compat': None,
                    }
                    script, output = Path(temp) / 'script.py', Path(temp) / 'result'
                    prepared = rhino.prepare(kind, script, output, target, 'ironpython')
                    with patch.dict(sys.modules, modules), \
                            patch('platform.python_implementation', return_value='IronPython'), \
                            patch('sys.stdout', io.StringIO()):
                        if kind == 'smoke20':
                            with self.assertRaisesRegex(RuntimeError, 'intentional stop before geometry'):
                                exec(compile(script.read_text(), str(script), 'exec'), {})
                        else:
                            exec(compile(script.read_text(), str(script), 'exec'), {})
                    self.assertEqual(prepared['compatibility_target'], target)
                    if kind == 'smoke20':
                        report = json.loads((output / 'report.json').read_text())
                        self.assertEqual(report['compatibility_target'], target)
                        self.assertEqual(report['state'], 'running')
                        self.assertEqual(report['cases'], [])
                        self.assertEqual(stopped, ['before_geometry'])
                        runtime = report['runtime']
                    else:
                        runtime = json.loads(output.read_text())
                        self.assertEqual(stopped, [])
                    self.assertEqual(runtime['rhino_major'], 8)
                    self.assertEqual(runtime['rhino_service_release'], 30)
                    self.assertEqual(runtime['rhino_build'], '8.30.test')

    def test_file_version_wins_over_folder_name(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / 'Rhino 5.app'
            executable = fake_app(app)
            info = rhino.installation(app)
            self.assertEqual(info['major'], 8)
            self.assertEqual(info['executable'], str(executable))
            self.assertFalse(info['runtime_version_verified'])

    def test_custom_folder_finds_versions_without_running_programs_or_following_links(self):
        with tempfile.TemporaryDirectory(prefix='Rhino 目录 ') as temp:
            root = Path(temp)
            fake_app(root / 'nested/Rhino 7.app', '7.0')
            fake_app(root / 'Rhino 8.app')
            (root / 'TextEdit.app').mkdir()
            (root / 'alias').symlink_to(root / 'nested', target_is_directory=True)
            (root / 'RhinoInstaller.exe').write_bytes(b'installer')
            with patch.object(rhino.subprocess, 'run') as run:
                result = rhino.search_installations(root)
                run.assert_not_called()
            self.assertEqual([item['major'] for item in result['installations']], [8, 7])
            self.assertFalse(result['truncated'])
            self.assertEqual(result['errors'], [])
            for item in result['installations']:
                engines = [e['engine'] for e in item['python_entries']]
                self.assertEqual(engines, ['ironpython', 'cpython'] if item['major'] == 8 else ['ironpython'])
                self.assertFalse(any(e['runtime_verified'] for e in item['python_entries']))
            self.assertFalse(result['installations'][1]['bundled_mcp_supported'])

    def test_search_reports_incomplete_or_invalid_installations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = fake_app(root / 'deep/Rhino.app')
            result = rhino.search_installations(root, max_depth=1)
            self.assertTrue(result['truncated'])
            self.assertEqual(result['installations'], [])
            result = rhino.search_installations(root, max_entries=1)
            self.assertTrue(result['truncated'])
            self.assertLessEqual(result['scanned_entries'], 1)
            executable.unlink()
            result = rhino.search_installations(root)
            self.assertEqual(result['installations'], [])
            self.assertEqual(result['errors'][0]['error'], 'ValueError')
            with self.assertRaises(FileNotFoundError):
                rhino.search_installations(root / 'missing')
            with self.assertRaises(ValueError):
                rhino.search_installations(root, max_depth=-1)

    def test_bundle_executable_must_stay_inside_macos_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / 'Rhino.app'
            fake_app(app)
            metadata = app / 'Contents/Info.plist'
            info = plistlib.loads(metadata.read_bytes())
            info['CFBundleExecutable'] = '../outside'
            metadata.write_bytes(plistlib.dumps(info))
            with self.assertRaises(ValueError):
                rhino.installation(app)

    def test_windows_folder_finds_real_exe_and_uses_file_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'Rhino 8/System/Rhino.exe'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'fixture')
            with patch.object(rhino.subprocess, 'run', return_value=SimpleNamespace(stdout='6.35.0.0')) as run:
                result = rhino.search_installations(root)
            info = result['installations'][0]
            self.assertEqual(info['major'], 6)
            self.assertEqual(info['executable'], str(exe))
            self.assertEqual(info['python_entries'][0]['command'], '_-RunPythonScript')
            self.assertFalse(info['bundled_mcp_supported'])
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'powershell')

    def test_transport_requires_matching_live_evidence(self):
        self.assertEqual(rhino.choose_transport(8, 8), 'mcp')
        self.assertEqual(rhino.choose_transport(7, 8, True), 'python')
        self.assertEqual(rhino.choose_transport(7, 8, False), 'computer_use')
        # 旧版存在独立验证的 MCP 适配器时，同样优先使用。
        self.assertEqual(rhino.choose_transport(5, 5), 'mcp')
        with self.assertRaises(ValueError):
            rhino.choose_transport(9)

    def test_unsupported_plugin_install_never_launches_package_manager(self):
        with patch.object(rhino, 'installation', return_value={'major': 7, 'yak': 'yak'}), \
                patch.object(rhino.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                rhino.install_mcp('app')
            run.assert_not_called()

    def test_prepare_is_self_contained_and_refuses_replay(self):
        with tempfile.TemporaryDirectory(prefix='rhino test ') as temp:
            script, output = Path(temp) / '测试.py', Path(temp) / '结果'
            value = rhino.prepare('smoke20', script, output, 5)
            source = script.read_text()
            self.assertIn('def run(', source)
            self.assertIn('compatibility_target=5', source)
            self.assertIn(str(script), value['macro'])
            compile(source, str(script), 'exec')
            with self.assertRaises(ValueError):
                rhino.prepare('smoke20', script, output, 5)
            self.assertEqual(script.read_text(), source)
            output.mkdir()
            with self.assertRaises(ValueError):
                rhino.prepare('smoke20', Path(temp) / 'other.py', output, 5)
            self.assertFalse((Path(temp) / 'other.py').exists())
            with self.assertRaises(ValueError):
                rhino.python_macro(script, 7, 'cpython')

    def test_macro_rejects_command_injection_path(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'bad"path.py'
            script.touch()
            with self.assertRaises(ValueError):
                rhino.python_macro(script, 8)


class ArchiveBoundaries(unittest.TestCase):
    def test_reader_follows_case_variant_redirect_and_preserves_python_indentation(self):
        data = io.BytesIO()
        base = 'https://docs.mcneel.com/rhino/8/help/en-us/'
        with zipfile.ZipFile(data, 'w') as z:
            z.writestr('index.json', json.dumps([{'path': p, 'url': base+p} for p in ['start.htm', 'target.htm']]))
            z.writestr('html/start.htm', '<meta content="0; URL=TARGET.htm#code" http-equiv="refresh">')
            z.writestr('text/start.htm.txt', 'Redirecting')
            z.writestr('html/target.htm', '<pre><code>if True:\n    result = 3 &lt; 4\n</code></pre>')
            z.writestr('text/target.htm.txt', 'Actual reference body')
        with zipfile.ZipFile(data) as z:
            result = docs.read_topic(z, 'START.htm')
        self.assertEqual(result['path'], 'target.htm')
        self.assertEqual(result['text'], 'Actual reference body')
        namespace = {}
        exec(compile(result['code_blocks'][0], 'example.py', 'exec'), namespace)
        self.assertIs(namespace['result'], True)

    def test_reader_missing_target_or_cycle_never_reports_placeholder_success(self):
        for target, exception in [('missing.htm', FileNotFoundError), ('start.htm', ValueError)]:
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as z:
                z.writestr('index.json', json.dumps([{'path': 'start.htm', 'url': 'https://docs.mcneel.com/start.htm'}]))
                z.writestr('html/start.htm', '<meta http-equiv="refresh" content="0;url='+target+'">')
                z.writestr('text/start.htm.txt', 'Redirecting')
            with zipfile.ZipFile(data) as z, patch.object(docs, 'fetch') as fetch:
                with self.assertRaises(exception):
                    docs.read_topic(z, 'start.htm')
                fetch.assert_not_called()

    def test_partial_archive_requires_opt_in_and_records_every_missing_topic(self):
        base = 'https://docs.mcneel.com/rhino/5/help/en-us/'
        def fetch(url):
            if 'missing' in url:
                raise OSError('unavailable official topic')
            return b'<html><title>Box</title><p>Full body.</p><script>hidden</script></html>'
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(docs, 'indexed_topics', return_value=([base+'box.htm', base+'missing.htm'], {})), \
                patch.object(docs, 'fetch', side_effect=fetch):
            output = Path(temp) / 'help.zip'
            with self.assertRaises(RuntimeError):
                docs.mirror(base, output, 1)
            self.assertFalse(output.exists())
            summary = docs.mirror(base, output, 1, allow_missing=True)
            self.assertFalse(summary['complete_index_coverage'])
            self.assertEqual((summary['topics'], summary['missing_topics']), (1, 1))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(json.loads(archive.read('missing.json'))[0]['url'], base+'missing.htm')
                body = archive.read('text/box.htm.txt').decode()
                self.assertIn('Full body.', body)
                self.assertNotIn('hidden', body)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **kwargs):
        return self.value


class ProtocolBoundaries(unittest.TestCase):
    def test_business_failure_is_not_mcp_success(self):
        for value in [
            {'isError': True, 'content': []},
            {'content': [{'type': 'text', 'text': '{"success":false,"message":"bad geometry"}'}]},
            {'structuredContent': {'result': {'success': False}}, 'content': []},
        ]:
            with self.assertRaises(RuntimeError):
                mcp_client.decoded(FakeResult(value))
        self.assertEqual(mcp_client.decoded(FakeResult({'content': [], 'isError': False})),
                         {'content': [], 'isError': False})

    def test_nested_async_error_keeps_the_actual_failure(self):
        error = ExceptionGroup('transport', [ExceptionGroup('session', [ValueError('invalid geometry')])])
        self.assertEqual(mcp_client.error_messages(error), ['ValueError: invalid geometry'])

    def test_failed_mutation_is_dispatched_once_and_stops_batch(self):
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        calls = []
        @asynccontextmanager
        async def transport(params):
            yield None, None
        class Session:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def initialize(self):
                return None
            async def list_tools(self):
                return SimpleNamespace(tools=[SimpleNamespace(name='create')])
            async def call_tool(self, name, arguments):
                calls.append((name, arguments))
                raise TimeoutError('response unknown')
        with patch.object(mcp_client, 'stdio_client', transport), patch.object(mcp_client, 'ClientSession', Session):
            with self.assertRaises(TimeoutError):
                asyncio.run(mcp_client.request('fake', [{'name': 'create'}, {'name': 'create'}]))
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
