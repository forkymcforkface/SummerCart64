"""Focused ODDR guard fixtures; generated files use an explicit ignored output.

These tests exercise patch staging, metadata identity and rejection reporting,
without compiling nextpnr or qualifying a hardware configuration.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from failure_check import require_rejection

HERE=Path(__file__).resolve().parent


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=OUTPUT)
        self.work=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self,name,*args):
        return subprocess.run([sys.executable,'-B',str(HERE/name),*map(str,args)],capture_output=True,text=True)

    def patch_fixture(self):
        root=self.work/'machxo2';root.mkdir()
        tree=ast.parse((HERE/'apply.py').read_text())
        originals={}
        for node in tree.body:
            if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='edit':
                name,anchor=map(ast.literal_eval,node.value.args[:2])
                originals.setdefault(name,[]).append(anchor)
        for name,anchors in originals.items():
            (root/name).write_text('\n'.join(anchors))
        return root

    def test_patch_success_and_reapply_refusal(self):
        root=self.patch_fixture()
        result=self.run_script('apply.py',self.work)
        self.assertEqual(result.returncode,0,result.stderr)
        saved={p:p.read_bytes() for p in root.iterdir()}
        self.assertNotEqual(self.run_script('apply.py',self.work).returncode,0)
        self.assertEqual(saved,{p:p.read_bytes() for p in root.iterdir()})

    def test_late_anchor_failure_writes_nothing(self):
        root=self.patch_fixture()
        path=root/'main.cc'
        path.write_text(path.read_text().replace('void MachXO2CommandHandler::customAfterLoad(Context *ctx)','void changed(Context *ctx)'))
        saved={p:p.read_bytes() for p in root.iterdir()}
        self.assertNotEqual(self.run_script('apply.py',self.work).returncode,0)
        self.assertEqual(saved,{p:p.read_bytes() for p in root.iterdir()})

    def metadata_fixture(self):
        wrapper=self.work/'wrapper.v';source=self.work/'in.json'
        wrapper.write_text('/* synthesis ICP_CURRENT="9" */\n/* synthesis LPF_RESISTOR="72" */')
        source.write_text(json.dumps({'modules':{'top':{'cells':{'p.PLLInst_0':{'type':'EHXPLLJ'}}}}}))
        return wrapper,source,self.work/'out.json',self.work/'manifest.json'

    def test_metadata_hash_and_values(self):
        paths=self.metadata_fixture();original=paths[1].read_bytes()
        result=self.run_script('preserve_pll_metadata.py',*paths)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(paths[1].read_bytes(),original)
        manifest=json.loads(paths[3].read_text())
        self.assertEqual(manifest['input_json_sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(manifest['attributes'],{'ICP_CURRENT':9,'LPF_RESISTOR':72})

    def test_metadata_aliases_do_not_write(self):
        paths=self.metadata_fixture()
        for left,right in [(0,2),(0,3),(1,2),(1,3),(2,3)]:
            args=list(paths);args[right]=args[left]
            before={p:p.read_bytes() for p in paths if p.exists()}
            self.assertNotEqual(self.run_script('preserve_pll_metadata.py',*args).returncode,0)
            self.assertEqual(before,{p:p.read_bytes() for p in paths if p.exists()})

    def test_metadata_hardlink_alias(self):
        paths=self.metadata_fixture();os.link(paths[1],paths[2])
        saved=paths[1].read_bytes()
        self.assertNotEqual(self.run_script('preserve_pll_metadata.py',*paths).returncode,0)
        self.assertEqual(paths[1].read_bytes(),saved)
        self.assertFalse(paths[3].exists())

    def test_exact_rejection(self):
        log=self.work/'failure.log';cfg=self.work/'forbidden.config'
        log.write_text('ERROR: expected barrier.\n')
        require_rejection(125,log,cfg,'expected barrier.')
        for code,message in [(1,'expected barrier.'),(0,'expected barrier.'),(125,'other failure.')]:
            log.write_text('ERROR: '+message+'\n')
            with self.assertRaises(AssertionError):
                require_rejection(code,log,cfg,'expected barrier.')
        log.write_text('ERROR: expected barrier.\n');cfg.write_text('partial output')
        with self.assertRaises(AssertionError):
            require_rejection(125,log,cfg,'expected barrier.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args();OUTPUT=args.output.resolve()
    if HERE.parents[1] == OUTPUT or HERE.parents[1] in OUTPUT.parents:
        parser.error('output must be outside tests/open-toolchain')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    unittest.main(argv=[sys.argv[0]])
