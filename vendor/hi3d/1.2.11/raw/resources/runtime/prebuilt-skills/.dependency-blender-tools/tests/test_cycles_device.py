import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cycles_device import select_cycles_device,cycles_device_context

class Preferences:
    compute_device_type='NONE'
    def __init__(self,available):
        self.available=available;self.calls=[];self.devices=[NS(id='cpu',name='CPU',type='CPU',use=True)]
    def get_devices(self):
        backend=self.compute_device_type;self.calls.append(backend)
        if backend not in self.available:raise TypeError('Backend unavailable')
        self.devices=[NS(id=d.id,name=d.name,type=d.type,use=d.use) for d in self.devices]
        self.devices.extend(NS(id=name,name=name,type=backend,use=False) for name in self.available[backend])

class Devices(unittest.TestCase):
    def setUp(self):self.scene=NS(cycles=NS(device='CPU'))
    def test_auto_order_and_explicit_request(self):
        prefs=Preferences({'METAL':['fixture GPU']})
        with patch('cycles_device._preferences',return_value=prefs):
            r=select_cycles_device(self.scene,'AUTO')
            self.assertEqual(prefs.calls,['OPTIX','CUDA','METAL']);self.assertEqual(r,{'backend':'METAL','devices':['fixture GPU'],'fallback':False})
            self.assertEqual(self.scene.cycles.device,'GPU');self.assertEqual([d.use for d in prefs.devices],[False,True])
    def test_fallback_is_explicit_and_invalid_names_never_mutate(self):
        prefs=Preferences({})
        with patch('cycles_device._preferences',return_value=prefs):
            with self.assertRaises(RuntimeError):select_cycles_device(self.scene,'METAL')
            r=select_cycles_device(self.scene,'METAL',fallback_cpu=True)
            self.assertTrue(r['fallback']);self.assertEqual(r['backend'],'CPU')
            before=prefs.compute_device_type
            with self.assertRaises(ValueError):select_cycles_device(self.scene,'INVALID',fallback_cpu=True)
            self.assertEqual(before,prefs.compute_device_type)
    def test_context_restores_reenumerated_and_new_devices_on_failure(self):
        for fail in [False,True]:
            prefs=Preferences({'METAL':['fixture GPU']})
            with patch('cycles_device._preferences',return_value=prefs):
                try:
                    with cycles_device_context(self.scene,'METAL') as r:
                        self.assertEqual(r['backend'],'METAL')
                        if fail:raise KeyboardInterrupt('fixture')
                except KeyboardInterrupt:pass
            self.assertEqual(self.scene.cycles.device,'CPU');self.assertEqual(prefs.compute_device_type,'NONE')
            self.assertEqual([d.use for d in prefs.devices],[True,False])

if __name__=='__main__':unittest.main()
