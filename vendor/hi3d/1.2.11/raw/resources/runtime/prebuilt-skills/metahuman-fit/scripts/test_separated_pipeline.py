"""Offline regression for ordered part/view handoffs; no credentials or network."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from image_pipeline import submit_arguments, generation_tick
from parts_generation import part_config, part_consents
from texture_pipeline import run, artifact, camera_values, call_stage
from fit import digest
from run import Journal, signature
import texture_pipeline


class SeparatedTests(unittest.TestCase):
    def test_query_error_resumes_existing_id_without_submit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();api=root/'api.py';api.touch()
            (root/'hi3d_job.json').write_text(json.dumps(dict(fingerprint='same',task_id='existing.id',state='processing',last_query_error={'type':'URLError'})))
            config=dict(image=str(root/'input.png'),hi3d_api_script=str(api))
            calls=[]
            def fake(command):
                calls.append(command)
                if '--dry-run' in command:return {'fingerprint':'same'}
                if 'wait' in command:return {'result':'pending'}
                self.fail('Recovery must not submit an existing task')
            result=generation_tick(config,root,fake)
            self.assertEqual(result['status'],'waiting_generation')
            self.assertEqual(result['task_id'],'existing.id')
            self.assertEqual(len(calls),2)

    def test_missing_parameters_surface_popup_without_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();api=root/'api.py';api.touch()
            config=dict(image=str(root/'input.png'),hi3d_api_script=str(api))
            calls=[]
            def fake(command):
                calls.append(command)
                if '--dry-run' in command:return {'fingerprint':'plan'}
                return {'result':'waiting_choice','stage':'parameters','user_interaction':{'kind':'preference'}}
            result=generation_tick(config,root,fake)
            self.assertEqual((result['status'],result['stage']),('waiting_choice','parameters'))
            self.assertNotIn('--billing-grant',calls[1])
            self.assertFalse((root/'hi3d_job.json').exists())

    def test_session_is_shared_across_new_parts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            config={'hi3d_session':str(root/'session.json'),'parts':{'bald':{},'hair':{}}}
            consents=part_consents(config,root)
            self.assertEqual(consents['bald'],{'hi3d_session':str(root/'session.json')})
            self.assertEqual(consents['hair'],{'hi3d_session':str(root/'session.json')})
            self.assertEqual(part_consents({'parts':{'bald':{}}},root),{'bald':{}})

    def test_hidden_hair_is_required_not_a_second_camera(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp)/'hair.png';image.write_bytes(b'image')
            config = {'hi3d_api_script': '/explicit/api.py', 'parts': {
                'hair': {'gray_views': {'front': str(image)}}}}
            with self.assertRaisesRegex(ValueError, 'behind'):
                part_config(config, 'hair')
            config['parts']['hair']['occluded_hair_completed'] = True
            plan = part_config(config, 'hair')
            plan['gray_views']['back'] = str(image)
            command = submit_arguments(plan, Path(temp)/'job.json')
            self.assertEqual(command[command.index('--views')+1], 'front,back')
            self.assertEqual(command.count('--image'), 2)
            self.assertIn('request_type=1', command)
            self.assertIn('resolution=2048quality', command)
            self.assertIn('face=5000000', command)
            self.assertFalse(any(s.startswith('pbr=') for s in command))

    def test_texture_handoff_keeps_back_slot_and_exact_uv_mesh(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();src=root/'high.glb';src.write_bytes(b'original high')
            front=root/'front.png';front.write_bytes(b'front')
            back=root/'back.png';back.write_bytes(b'back')
            calls=[]
            def fake(config, output, journal, name, service, request):
                calls.append((service, request));folder=output/name;folder.mkdir()
                (folder/'artifacts').mkdir();files=[]
                def add(field,index=None):
                    path=folder/'artifacts'/(field+str(index)+'.bin');path.write_bytes((field+str(index)).encode())
                    files.append(dict(field_path=[field] if index is None else [field,index],file=path.name,sha256=digest(path)))
                result={'success':True}
                if name=='uv':add('uv_mesh_glb')
                elif name=='render':
                    for field in ('normal_images','ccm_images','mask_images'):
                        for i in range(4):add(field,i)
                    result.update(camera_azims=[0,90,180,270],camera_elevs=[0]*4,view_weights=[1]*4)
                elif name=='multiview':
                    for i in range(4):add('generated_images',i)
                else:
                    for field in ('baked_glb','texture_image','coverage_mask'):add(field)
                    result['coverage']=.91
                (folder/'invocation.json').write_text(json.dumps(dict(status='SUCCEEDED',files=files)))
                return folder,result
            config=dict(part='hair',occluded_hair_completed=True,high_glb=str(src),
                        color_views=dict(front=str(front),back=str(back)),output=str(root/'output'))
            result=run(config, fake)
            self.assertEqual([c[0] for c in calls],['texture-uv-unwrap-v3-0','texture-render-v3-0','multiview-service','texture-bake-v3-0'])
            refs=calls[2][1]['reference_images']
            self.assertEqual(refs,[{'$file':str(front)},None,{'$file':str(back)},None])
            self.assertEqual(calls[1][1]['mesh_glb'],calls[3][1]['mesh_glb'])
            self.assertFalse(calls[0][1]['need_repair'])
            self.assertEqual(result['status'],'needs_visual_review')
            self.assertFalse(result['geometry_preservation_verified'])
            Path(result['albedo']).write_bytes(b'modified')
            with self.assertRaisesRegex(ValueError,'modified'):
                artifact(root/'output/bake','texture_image')

    def test_camera_summary_must_be_actual_ordered_finite_values(self):
        for invalid in (None, {'shape':[4]}, [0,90], [0,90,float('nan'),270]):
            with self.assertRaises(ValueError):
                camera_values(dict(camera_azims=invalid,camera_elevs=[0]*4,view_weights=[1]*4))

    def test_ambiguous_existing_invocation_is_never_resubmitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();script=root/'mdf.py';script.write_text('# mock')
            config={'mdf_call_script':str(script)};request={'resolution':1024};service='texture-render-v3-0'
            key=signature({'service':service,'request':request,'endpoint':None},[])
            folder=root/('render-'+key[:16]);folder.mkdir()
            (folder/'invocation.json').write_text(json.dumps({'status':'IN_PROGRESS'}))
            with patch('texture_pipeline.subprocess.run') as launch:
                with self.assertRaisesRegex(RuntimeError,'original MDF trace'):
                    call_stage(config,root,Journal(root),'render',service,request)
                launch.assert_not_called()

if __name__=='__main__':unittest.main()
