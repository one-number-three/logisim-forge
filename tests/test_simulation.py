"""Integration tests use the installed Logisim-ITA binary when available."""
import csv
import os
import tempfile
import unittest
from pathlib import Path

from logisim_forge import Circuit, simulate, inspect
from logisim_forge.verify import find_jar, dump, parse


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            find_jar()
        except RuntimeError:
            raise unittest.SkipTest('set LOGISIM_JAR to a Logisim-ITA binary')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, content):
        path = self.root / name
        path.write_text(content, encoding='utf-8')
        return str(path)

    def test_not_gate_and_negative_controls(self):
        c = Circuit('main')
        c.pin((100, 100), 'A'); c.not_gate((200, 100)); c.pin((300, 100), 'Y', 'out', 'west')
        c.wire((100, 100), (170, 100)); c.wire((200, 100), (300, 100))
        p = self.write('not.circ', c.to_xml())
        vectors = self.write('vectors.csv', 'A,Y\n0,1\n1,0\n')
        result = simulate(p, 'main', vectors, str(self.root / 'view.png'))
        self.assertTrue(result['ok'], result['diagnostics'])
        self.assertEqual(result['rows'], 2)
        self.assertTrue((self.root / 'view.png').is_file())
        self.assertFalse(simulate(p, 'main', self.write('bad.csv', 'A,Y\n0,0\n'))['ok'])
        self.assertFalse(simulate(p, 'main', self.write('empty.csv', 'A,Y\n'))['ok'])
        self.assertFalse(simulate(p, 'main', self.write('short.csv', 'A,Y\n1\n'))['ok'])
        self.assertFalse(simulate(p, 'main', self.write('invalid.csv', 'A,Y\n2,0\n'))['ok'])
        self.assertFalse(simulate(p, 'missing', vectors)['ok'])
        self.assertTrue(inspect(p)['ok'])

    def test_d_flip_flop_retains_state_between_rows(self):
        # The ITA default symbol puts CLK at (340,150) and D at (340,190).
        c = Circuit('main')
        c.pin((100, 100), 'CLK'); c.pin((100, 190), 'D')
        c.pin((500, 150), 'Q', 'out', 'west')
        xml = c.to_xml().replace('source="2.7.1"', 'source="2.16.1.4"')
        xml = xml.replace('<main name="main"/>', '<lib name="4" desc="#Memory"/><main name="main"/>', 1)
        parts = '''<comp lib="4" name="D Flip-Flop" loc="(400,150)"/>
        <comp lib="1" name="Ground" loc="(370,130)"/>
        <comp lib="1" name="Ground" loc="(370,210)"/>
        <wire from="(100,100)" to="(300,100)"/><wire from="(300,100)" to="(300,150)"/>
        <wire from="(300,150)" to="(340,150)"/><wire from="(100,190)" to="(340,190)"/>
        <wire from="(400,150)" to="(500,150)"/>'''
        p = self.write('flipflop.circ', xml.replace('</circuit>', parts + '</circuit>'))
        vectors = self.write('clock.csv', 'CLK,D,Q\n0,0,0\n0,1,0\n1,1,1\n1,0,1\n0,0,1\n1,0,0\n')
        result = simulate(p, 'main', vectors)
        self.assertTrue(result['ok'], result['diagnostics'])
        self.assertEqual(result['rows'], 6)

    def test_gate_geometry_matches_real_loader(self):
        for name, inputs in [('AND Gate', 6), ('AND Gate', 7), ('NOR Gate', 2), ('XOR Gate', 2), ('XNOR Gate', 2)]:
            with self.subTest(name=name, inputs=inputs):
                c=Circuit('main')
                gate=c._add(2,name,(400,300),[('inputs',str(inputs)),('negate0','true')])
                expected=set(c.ports()[id(gate)])
                nl=parse(dump(self.write('ports.circ',c.to_xml())))
                loaded=next(item for item in nl.components if item['name']==name)
                self.assertEqual(expected,{p for p,_,_ in loaded['ports']})

if __name__ == '__main__':
    unittest.main()
