import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image
import imageio_ffmpeg
from encode_sequence import encode_sequence, sequence_names


class SequenceTests(unittest.TestCase):
    def test_png_and_jpeg_nonzero_start_real_decode_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for extension in ['png','jpg','jpeg']:
                frames = root/extension; frames.mkdir()
                for i in range(7,10): Image.new('RGB',(16,18),(i*20,60,80)).save(frames/f'{i:04d}.{extension}')
                video = root/(extension+'.mp4')
                args = dict(start=7,pattern='%04d.'+extension,crf=20)
                result = encode_sequence(imageio_ffmpeg.get_ffmpeg_exe(),frames,8,video,**args)
                self.assertEqual(result['actual']['frames'],3)
                self.assertAlmostEqual(result['actual']['duration_seconds'],.375,places=3)
                with self.assertRaises(FileExistsError):
                    encode_sequence(imageio_ffmpeg.get_ffmpeg_exe(),frames,8,video,**args)

    def test_invalid_sequences_and_explicit_padding(self):
        for names in [[],['0001.jpg','0003.jpg'],['0001.jpg','0002.png']]:
            with self.assertRaises(ValueError): sequence_names(names,start=1,pattern='%04d.jpg')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frame = root/'0001.jpg'; video = root/'video.mp4'
            frame.write_bytes(b'broken jpeg')
            with self.assertRaises(OSError): encode_sequence('not-invoked',root,8,video,start=1,pattern='%04d.jpg')
            Image.new('RGB',(15,17)).save(frame)
            with self.assertRaises(ValueError): encode_sequence('not-invoked',root,8,video,start=1,pattern='%04d.jpg')
            result = encode_sequence(imageio_ffmpeg.get_ffmpeg_exe(),root,8,video,start=1,pattern='%04d.jpg',pad_even=True)
            self.assertEqual((result['expected']['width'],result['expected']['height']),(16,18))
            Image.new('RGB',(16,18)).save(root/'0002.jpg')
            with self.assertRaises(ValueError): encode_sequence('not-invoked',root,8,video,start=1,pattern='%04d.jpg',pad_even=True)

if __name__ == '__main__': unittest.main()
