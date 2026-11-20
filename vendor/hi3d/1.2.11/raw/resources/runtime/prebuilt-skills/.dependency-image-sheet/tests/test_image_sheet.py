import sys, unittest, tempfile, hashlib, json, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image
from image_sheet import compose_sheet, write_sheet


class SheetTests(unittest.TestCase):
    def test_bottom_labels_preserve_image_area_and_cell_mapping(self):
        source = Image.new('RGB', (40, 20), 'red')
        sheet, cells = compose_sheet([dict(image=source, label='A')], columns=1,
            image_size=(40, 20), label_height=16, gap=2, label_position='bottom')
        self.assertEqual(sheet.size, (44, 40))
        self.assertEqual(cells[0]['image_box'], [2, 2, 42, 22])
        self.assertEqual(cells[0]['cell_box'], [2, 2, 42, 38])
        self.assertEqual(sheet.crop((2, 2, 42, 22)).tobytes(), source.tobytes())
        self.assertGreater(len(set(sheet.crop((2, 22, 42, 38)).getdata())), 1)
        with self.assertRaises(ValueError):
            compose_sheet([dict(image=source)], columns=1, image_size=(40, 20),
                          label_height=16, label_position='side')

    def test_order_proportions_and_original_pixels(self):
        wide = Image.new('RGB',(40,20),'red'); tall = Image.new('RGB',(10,30),'blue')
        originals = [im.tobytes() for im in [wide,tall]]
        sheet,cells = compose_sheet([dict(image=wide,label='wide'),dict(image=tall,label='tall')],
                    columns=2,image_size=(20,20),label_height=8,gap=2)
        self.assertEqual(sheet.size,(46,32))
        self.assertEqual([c['label'] for c in cells],['wide','tall'])
        self.assertEqual(cells[0]['image_box'],[2,10,22,20])
        self.assertEqual(cells[1]['image_box'],[24,10,31,30])
        self.assertEqual(sheet.getpixel((3,18)),(255,0,0))
        self.assertEqual(sheet.getpixel((25,18)),(0,0,255))
        self.assertEqual(originals,[im.tobytes() for im in [wide,tall]])
        _,stretched = compose_sheet([dict(image=wide)],columns=1,image_size=(20,20),label_height=0,resize='stretch')
        self.assertEqual(stretched[0]['image_box'],[0,0,20,20])

    def test_failure_hash_and_output_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.png'; output=root/'sheet.png'
            Image.new('RGB',(20,10)).save(source)
            args=dict(columns=1,image_size=(20,20),label_height=8)
            for items in [[],[dict(path=source,sha256='wrong')]]:
                with self.assertRaises(ValueError): write_sheet(items,output,**args)
                self.assertFalse(output.exists())
            with self.assertRaises(ValueError): write_sheet([dict(path=source)],source,overwrite=True,**args)
            source.write_bytes(b'broken')
            with self.assertRaises(OSError): write_sheet([dict(path=source)],output,**args)
            Image.new('RGB',(20,10)).save(source)
            write_sheet([dict(path=source,sha256=hashlib.sha256(source.read_bytes()).hexdigest())],output,**args)
            with self.assertRaises(FileExistsError): write_sheet([dict(path=source)],output,**args)

    def test_standalone_manifest_cli_and_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.png'; Image.new('RGB',(20,10)).save(source)
            manifest=root/'images.json'; manifest.write_text(json.dumps(dict(images=[dict(path='source.png',label='side')],layout=dict(columns=1,image_size=[20,20],label_height=8))))
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/image_sheet.py'),
                     '--manifest',str(manifest),'--output',str(root/'sheet.png'),'--mapping',str(root/'mapping.json')]
            subprocess.run(command,check=True,capture_output=True)
            mapping=json.loads((root/'mapping.json').read_text())
            self.assertEqual(mapping['cells'][0]['source'],str(source.resolve()))
            self.assertEqual(mapping['cells'][0]['label'],'side')
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)

if __name__ == '__main__': unittest.main()
