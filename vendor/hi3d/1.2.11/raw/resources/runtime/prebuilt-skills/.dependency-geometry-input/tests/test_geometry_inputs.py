import io
import sys
from pathlib import Path
import tempfile
import unittest
import zipfile
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from geometry_inputs import prepare_image, read_bridge, build_prep_zip, main


def png(color='white'):
    buffer=io.BytesIO()
    Image.new('RGB',(4,4),color).save(buffer,format='PNG')
    return buffer.getvalue()


def bridge_zip(count=4, duplicate=False, missing=False):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for i in range(count):
            z.writestr(f'normal_v{i}_view.png',png())
            z.writestr(f'ccm_v{i}_view.png',png())
            if not (missing and i==1):
                z.writestr(f'View{i}_CCM.exr',b'v/1\x01'+bytes([i]))
            z.writestr(f'View{i}_GrayMask.png',png())
        z.writestr('camera_info.txt',b'camera fixture')
        if duplicate:z.writestr('nested/normal_v0_duplicate.png',png())
    return buffer.getvalue()


class GeometryInputsTests(unittest.TestCase):
    def test_alpha_and_white_composite_stay_aligned(self):
        image=Image.new('RGBA',(4,4),(0,0,0,0))
        for x in [1,2]:
            for y in [1,2]:image.putpixel((x,y),(255,0,0,128))
        rgb,rgba=prepare_image(image,size=4,padding=2)
        self.assertEqual(rgba.getpixel((1,1)),(255,0,0,128))
        self.assertEqual(rgb.getpixel((1,1)),(255,127,127))
        self.assertEqual(rgb.getpixel((0,0)),(255,255,255))
        self.assertEqual(rgba.getpixel((0,0))[3],0)
        self.assertEqual(image.getpixel((1,1))[3],128)

    def test_rejects_missing_empty_or_full_mask(self):
        for im in [Image.new('RGB',(3,3)),Image.new('RGBA',(3,3),(0,0,0,0)),
                   Image.new('RGBA',(3,3),(0,0,0,255))]:
            with self.subTest(mode=im.mode),self.assertRaises(ValueError):prepare_image(im)

    def test_rejects_invalid_configuration(self):
        im=Image.new('RGBA',(3,3),(1,2,3,128))
        for kw in [{'size':0},{'size':True},{'padding':0.5},{'padding':float('nan')}]:
            with self.subTest(kw=kw),self.assertRaises(ValueError):prepare_image(im,**kw)

    def test_bridge_preserves_order_ccm_and_camera(self):
        bridge=read_bridge(bridge_zip(),count=4)
        colors=[png(c) for c in ['red','blue','green','yellow']]
        out=build_prep_zip(colors,bridge)
        with zipfile.ZipFile(io.BytesIO(out)) as z:
            self.assertEqual(z.read('View0_GrayColor.png'),colors[0])
            self.assertEqual(z.read('View1_GrayColor.png'),colors[1])
            self.assertEqual(z.read('View1_CCM.exr'),b'v/1\x01\x01')
            self.assertEqual(z.read('camera_info.txt'),b'camera fixture')
            self.assertFalse(any(n.endswith('.glb') for n in z.namelist()))

    def test_rejects_ambiguous_or_incomplete_bridge(self):
        for content in [bridge_zip(duplicate=True),bridge_zip(missing=True)]:
            with self.assertRaises(ValueError):read_bridge(content,count=4)

    def test_rejects_wrong_view_count_and_png_disguised_as_exr(self):
        bridge=read_bridge(bridge_zip(),count=4)
        with self.assertRaises(ValueError):build_prep_zip([png()],bridge)
        bridge['ccm_exr'][0]=png()
        with self.assertRaises(ValueError):build_prep_zip([png()]*4,bridge)

    def test_rejects_nonstandard_counts_without_face_metadata(self):
        for count in [3,5]:
            bridge=read_bridge(bridge_zip(count=count),count=count)
            with self.assertRaises(ValueError):build_prep_zip([png()]*count,bridge)

    def test_cli_refuses_overwrite_after_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            im=Image.new('RGBA',(3,3),(20,30,40,128));im.save(root/'input.png')
            argv=['prepare','--input',str(root/'input.png'),'--out',str(root/'prepared'),'--size','8']
            self.assertEqual(main(argv),0)
            original=(root/'prepared/prepared_rgba.png').read_bytes()
            with self.assertRaises(FileExistsError):main(argv)
            self.assertEqual((root/'prepared/prepared_rgba.png').read_bytes(),original)


if __name__=='__main__':unittest.main()
