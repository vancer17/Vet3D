"""Assemble final lowpoly evidence and artifact links without publication side effects."""
import json
from pathlib import Path
import tempfile
import sys
from PIL import Image
from image_sheet import write_sheet


def montage(root, rows, path, size=440):
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('A nonempty rectangular montage is required')
    return write_sheet([dict(path=root/filename,label=label) for row in rows for filename,label in row],
                       path, columns=len(rows[0]), image_size=(size,size), label_height=36,
                       background='#101722', foreground='#dce8ef', font_size=18,
                       label_offset=(12,9), resize='stretch', resample=Image.Resampling.BICUBIC,
                       overwrite=True, save_options={'quality':94})


def package(config):
    root = Path(config['output']); review = root / 'review'
    montage(review, [[(v + '_' + angle + '.png', v + ' / ' + angle)
        for v in ['high', 'lowpoly']] for angle in ['front', 'threequarter', 'side']], review / 'comparison.jpg')
    montage(review, [[('lowpoly_' + state + '.png', state)
        for state in ['front', 'eyeBlink_L', 'mouthSmile', 'jawOpen']]], review / 'expressions.jpg', 360)
    if config.get('video_frames_per_control', 0):
        frames = json.loads((review / 'frames.json').read_text())
        from encode_sequence import encode_sequence
        if not frames:
            raise ValueError('Requested expression video requires nonempty frames.json')
        with tempfile.TemporaryDirectory(prefix='video-frames-', dir=review) as folder:
            video_dir = Path(folder)
            for frame in frames:
                i = frame['index']
                montage(review, [[(f'lowpoly_{i:04d}.png', frame['control'])]], video_dir / f'{i:04d}.jpg', 480)
            checked = encode_sequence(config['ffmpeg'], video_dir, 8, review / 'expressions.mp4',
                                      start=min(f['index'] for f in frames), pattern='%04d.jpg',
                                      crf=20, overwrite=True)
        (review / 'expressions.video.json').write_text(json.dumps(checked, indent=2))
    delivery = json.loads((root / 'delivery.json').read_text())
    validation = json.loads((root / 'lowpoly_validation.json').read_text())['lowpoly']
    metrics = json.loads((root / 'metrics.json').read_text())
    low = delivery['lowpoly']
    contents = f'''# Lowpoly head review

High GLB → source-derived quad topology → facial loops and blendshapes → basic skinning → albedo / normal baking → GLB and Blender delivery.

- Head surface: {low['vertices']:,} vertices, {low['quads']:,} quads, {len(low['blendshapes'])} named blendshapes.
- Basic rig: {delivery['joints']} joints. This is not an ARKit 52 or production dental/tongue rig.
- Evaluated skin deformation: {validation['passed']}, {len(validation['states'])} states. Contact scope: {validation['scope']}.
- GLB reimport and all morph endpoints: {metrics['glb_roundtrip']['passed']}.
- Separate mesh hair: {len(delivery['hair']['parts'])} parts; see hair_report.json for counts and head-bone attachment. The skin collision report does not cover hair/skin intersections.

Open [GLB](Lowpoly_Rigged.glb) or [editable Blender project](Heads_Rigged.blend). The GLB includes UVs, embedded textures, skin and named morph targets; its triangles may duplicate vertices at UV/normal seams. The Blender project retains quads. [Albedo](textures/Lowpoly_BaseColor.png) is sRGB; [normal](textures/Lowpoly_Normal.png) is 16-bit tangent-space OpenGL +Y. Full original-high geometry is used for baking. Scalar material channels are retained without a redundant image where possible.

Review [three views](review/comparison.jpg), [expressions](review/expressions.jpg), and [quad wireframe](review/lowpoly_wire.png). Metrics and contact reports complement visual inspection; they do not establish arbitrary-expression or internal-part collision safety.

Data: lowpoly_data.npz stores neutral positions, ordered triangles/quads, expression_names and expression_deltas. It can be explicitly handed to a separate registration workflow. GNM and MetaHuman fitting are outside this workflow.

Timing: timing_summary.json is the latest attempt; timings.jsonl appends all stage attempts; workflow.json records dependencies and verified output hashes. Cached stages record measured cache verification time and the originating attempt, not historical compute time. Face annotation/setup and dependency installation are outside the automated run timer; record their actual intervals separately when performed. Token usage is not estimated.
'''
    (root / 'REVIEW.md').write_text(contents)
    print('PACKAGE_READY', root / 'REVIEW.md', flush=True)


if __name__ == '__main__':
    package(json.loads(Path(sys.argv[1]).read_text()))
