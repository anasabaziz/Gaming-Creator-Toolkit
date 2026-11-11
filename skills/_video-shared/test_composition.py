"""Synthetic behavioral checks for optional composition; never touches user media."""
import copy
import array
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import pipeline as p
from article_frames import extract


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path('tmp').mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix='composition-test-', dir='tmp')).resolve()
        cls.a = cls.root/'a.mkv'; cls.b = cls.root/'b.mkv'; cls.art = cls.root/'title.png'
        p.run([p.tool('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10',
               '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','ffv1','-c:a','pcm_s16le',cls.a])
        p.run([p.tool('ffmpeg'),'-v','error','-f','lavfi','-i','color=blue:size=320x180:rate=10','-t','3','-c:v','ffv1',cls.b])
        Image.new('RGB',(100,50),'red').save(cls.art)

    def manifest(self, name):
        job = self.root/name; m = p.init(self.a,job); m['format']['fps']='10'
        m['sources']={'other':{'path':str(self.b),'identity':p.fingerprint(self.b)}}
        m['outputs']=[{'id':'roundup','kind':'trailer','ordering':'custom','ordering_authorization':'Test requested two sources',
            'label_requirements':['First Game',None],
            'target_duration':2,'label_style':{'x':8,'y':130,'width':180,'height':40,'font_size':20},
            'segments':[{'in':0,'out':1,'label':{'text':'First Game'}},
                        {'source_id':'other','in':0,'out':1,'effects':[{'kind':'image','path':str(self.art),'identity':p.fingerprint(self.art,True),
                          'start':.2,'end':1,'x':110,'y':60,'width':100,'height':50,'fade_in':.2,'move_y':20,'blur_sigma':8,'blur_ramp':.5}]}]}]
        return job,m

    def test_render_reuse_and_asset_change(self):
        job,m=self.manifest('roundup'); path=job/'manifest.json'; p.write(path,m)
        p.render(path); checks=p.validation(path); p.report(path)
        self.assertEqual(checks[0]['integrity'],'passed')
        self.assertEqual(checks[0]['project_agreement'],'passed')
        old=p.read(job/'render-state.json')['outputs'][0]
        # Red supplied artwork visible at the reveal endpoint; blue remains before reveal.
        def pixel(t):
            raw=p.run([p.tool('ffmpeg'),'-v','error','-ss',str(t),'-i',old['mp4'],'-frames:v','1','-vf','crop=2:2:150:80','-f','rawvideo','-pix_fmt','rgb24','-'])
            return tuple(raw[:3])
        self.assertGreater(pixel(1.8)[0],200)
        self.assertGreater(pixel(1.0)[2],200)
        before={x.name:x.stat().st_mtime_ns for x in (job/'media').glob('*.mkv')}
        p.render(path)
        self.assertEqual(before,{x.name:x.stat().st_mtime_ns for x in (job/'media').glob('*.mkv')})
        art2=self.root/'title2.png'; Image.new('RGB',(100,50),'green').save(art2)
        e=m['outputs'][0]['segments'][1]['effects'][0]; e.update(path=str(art2),identity=p.fingerprint(art2,True))
        p.write(path,m);p.render(path)
        new=p.read(job/'render-state.json')['outputs'][0]
        self.assertNotEqual(old['mp4'],new['mp4'])
        self.assertEqual(old['media'][0]['sha256'],new['media'][0]['sha256'])
        self.assertTrue(all((job/'media'/name).stat().st_mtime_ns==mtime for name,mtime in before.items()))
        # Article extracts from chosen ORIGINAL recording, not rendered effects.
        requests=job/'shots.json';p.write(requests,[{'section_id':'section-1','time':.3,'source_id':'other','alt':'Blue test source'}])
        result=extract(path,requests,job/'images')
        with Image.open(job/'images'/result[0]['path']) as im:
            self.assertEqual(im.size,(320,180));self.assertGreater(im.getpixel((150,80))[2],200)

    def test_music_rows_and_rejections(self):
        job,m=self.manifest('music')
        m['outputs'][0]['music']={'path':str(self.a),'identity':p.fingerprint(self.a,True),'gain':.2,'authorization':'Synthetic soundtrack requested','credit':'Synthetic tone, generated for test'}
        path=job/'manifest.json';p.write(path,m);p.render(path);p.validation(path)
        state=p.read(job/'render-state.json')['outputs'][0]
        self.assertTrue(state['audio_expected'])
        self.assertTrue((Path(state['mp4']).parent/'MUSIC-CREDIT.txt').exists())
        raw=p.run([p.tool('ffmpeg'),'-v','error','-ss','1.2','-i',state['mp4'],'-t','0.5','-vn','-ac','1','-ar','48000','-f','s16le','-'])
        pcm=array.array('h',raw)
        self.assertGreater(max(abs(x) for x in pcm),100)
        self.assertTrue(210 <= sum(a<=0<b for a,b in zip(pcm,pcm[1:])) <= 230)
        # Full-width gameplay row over two independently cropped HUD panels.
        layout={'type':'rows','rows':[{'height':180,'panels':[{'rect':[0,0,180,180],'width':180}]},
                                     {'height':140,'panels':[{'rect':[0,0,90,140],'width':90},{'rect':[230,0,90,140],'width':90}]}]}
        vertical=copy.deepcopy(m);vertical['format'].update(width=180,height=320)
        vertical['vertical_authorization']='Synthetic portrait request'
        vertical['outputs']=[{'id':'rows','segments':[{'in':0,'out':.5,'layout':layout}]}]
        p.write(path,vertical);p.render(path);p.validation(path)
        bad=copy.deepcopy(layout);bad['rows'][1]['panels'][0]['width']=88
        with self.assertRaises(ValueError):p.layout_filter(bad,320,180,180,320)
        bad=copy.deepcopy(m);bad['sources']['other']['identity']['size']+=1
        with self.assertRaisesRegex(ValueError,'identity'):p.validate_manifest(bad)
        bad=copy.deepcopy(m);bad['outputs'][0]['segments'][1]['effects'][0]['identity']['size']+=1
        with self.assertRaisesRegex(ValueError,'Artwork'):p.validate_manifest(bad)
        bad=copy.deepcopy(m);bad['outputs'][0]['ordering']='chronological'
        with self.assertRaisesRegex(ValueError,'Roundups'):p.validate_manifest(bad)
        bad=copy.deepcopy(m);bad['outputs'][0]['segments'][0].pop('label')
        with self.assertRaisesRegex(ValueError,'Required label'):p.validate_manifest(bad)
        bad=copy.deepcopy(m);bad['outputs'][0]['segments'][0]['label']['start']=.2
        with self.assertRaisesRegex(ValueError,'Required label'):p.validate_manifest(bad)

    def test_progressive_blur(self):
        from PIL import ImageStat
        from composition import compose
        from types import SimpleNamespace
        job=self.root/'blur';job.mkdir()
        source=job/'checker.mkv';still=job/'checker.png'
        im=Image.new('RGB',(320,180))
        for y in range(180):
            for x in range(320):im.putpixel((x,y),(255,255,255) if (x//4+y//4)%2 else (0,0,0))
        im.save(still)
        p.run([p.tool('ffmpeg'),'-v','error','-loop','1','-i',still,'-t','2','-r','10','-c:v','ffv1',source])
        effect={'kind':'image','path':str(self.art),'start':.2,'end':2,'x':110,'y':60,'width':100,'height':50,'fade_in':.2,'blur_sigma':8,'blur_ramp':1}
        result=job/'composed.mkv';compose(source,[effect],result,'blur-test',2,{'fps':'10'},job,SimpleNamespace(**vars(p)))
        contrasts=[]
        for i,t in enumerate([0,.7,1.5]):
            frame=job/f'frame-{i}.png';p.run([p.tool('ffmpeg'),'-v','error','-ss',str(t),'-i',result,'-frames:v','1',frame])
            with Image.open(frame) as image:contrasts.append(ImageStat.Stat(image.crop((0,0,80,80)).convert('L')).stddev[0])
        self.assertGreater(contrasts[0],contrasts[1]);self.assertGreater(contrasts[1],contrasts[2]);self.assertLess(contrasts[2],10)

    def test_replacement_contract(self):
        job=self.root/'replacement-source';m=p.init(self.a,job)
        m['outputs']=[{'id':'clip','kind':'trailer','segments':[{'in':0,'out':1}]}]
        path=job/'manifest.json';p.write(path,m)
        selection=self.root/'replacements.json';layouts=self.root/'layouts.json'
        p.write(selection,{'clip':[{'in':1,'out':2,'replacement_reason':'Better portrait readability'}]})
        p.write(layouts,{'clip':[{'type':'crop','rect':[108,0,102,180]}]})
        with self.assertRaisesRegex(ValueError,'authorization'):
            p.derive(path,self.root/'denied','vertical',selections=selection,layout=layouts,authorization='Portrait requested')
        result=p.derive(path,self.root/'replaced','vertical',selections=selection,layout=layouts,authorization='Portrait requested',replacement_authorization='Applicable creator profile')
        changed=p.read(result['manifest'])
        self.assertEqual(changed['replacement_history'][0]['before'][0]['in'],0)
        self.assertEqual(changed['outputs'][0]['segments'][0]['in'],1)
        p.write(selection,{'clip':[{'in':1,'out':2.5,'replacement_reason':'Longer'}]})
        with self.assertRaisesRegex(ValueError,'frame count'):
            p.derive(path,self.root/'duration-denied','vertical',selections=selection,layout=layouts,authorization='Portrait requested',replacement_authorization='Profile')

    def test_preview_geometry_progress_and_dimensions(self):
        import job_helpers as h
        job,m=self.manifest('preview-master')
        path=job/'manifest.json';p.write(path,m)
        result=h.preview(path,self.root/'preview-derived',160)
        preview=p.read(result['manifest'])
        self.assertEqual(preview['format']['height'],90)
        self.assertEqual(preview['outputs'][0]['segments'][1]['effects'][0]['width'],50)
        self.assertEqual(preview['outputs'][0]['segments'][1]['effects'][0]['blur_sigma'],4)
        # Crop coordinates stay in source space and odd destination rounding is rejected.
        m['outputs']=[{'id':'crop','segments':[{'in':0,'out':1,'layout':{'type':'crop','rect':[0,0,320,180]}}]}]
        p.write(path,m)
        result=h.preview(path,self.root/'preview-crop',160)
        self.assertEqual(p.read(result['manifest'])['outputs'][0]['segments'][0]['layout']['rect'],[0,0,320,180])
        with self.assertRaises(ValueError):h.preview(path,self.root/'bad-preview',6)
        frame=self.root/'dimension-fixture.png';Image.new('RGB',(1672,941)).save(frame)
        self.assertEqual(h.dimensions(frame)['status'],'passed')
        self.assertEqual(h.dimensions(frame,exact=[1280,720])['status'],'failed')
        progress=[]
        p.run([p.tool('ffmpeg'),'-v','error','-i',self.a,'-t','1','-f','null','-'],progress=progress.append)
        self.assertGreater(progress[-1]['processed_media_seconds'],.8)
        self.assertGreaterEqual(progress[-1]['elapsed_seconds'],0)


if __name__=='__main__':unittest.main()
