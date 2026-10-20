import unittest
from sync import prepare, make_index

def row(id, **fields):
    return {"id": id, "fields": fields}

class TestSynchronisation(unittest.TestCase):
    def test_ajout_modification_et_preservation(self):
        source = [row(1, Code="04", Nom="Alpes", Autre="x"), row(2, Code="05", Nom="Hautes-Alpes")]
        target = [row(9, Code="04", Nom="Ancien", Projet="local")]
        creates, updates = prepare(source, target, ["Code"], ["Code", "Nom"])
        self.assertEqual(creates, [{"fields": {"Code": "05", "Nom": "Hautes-Alpes"}}])
        self.assertEqual(updates, [{"id": 9, "fields": {"Nom": "Alpes"}}])
    def test_reexecution_idempotente(self):
        src = [row(1, Code="04", Nom="Alpes")]
        target = [row(4, Code="04", Nom="Alpes")]
        self.assertEqual(prepare(src, target, ["Code"], ["Code", "Nom"]), ([], []))
    def test_doublon_rejete(self):
        with self.assertRaises(ValueError):
            make_index([row(1, Code="04"), row(2, Code="04")], ["Code"], "Source")
    def test_cle_vide_rejetee(self):
        with self.assertRaises(ValueError):
            make_index([row(1, Code="")], ["Code"], "Source")
    def test_colonne_absente_rejetee(self):
        with self.assertRaises(ValueError):
            prepare([row(1, Code="04")], [], ["Code"], ["Code", "Nom"])

if __name__ == "__main__":
    unittest.main()
