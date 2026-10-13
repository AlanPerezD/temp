import csv
import os
import tempfile
import unittest
from unittest import mock

import clean_leads as cl
import fetch_places as fp


class Phones(unittest.TestCase):
    def test_mobile_formats(self):
        for raw in ("987 654 321", "+51 987 654 321", "51987654321", "(+51) 987-654-321", "0051987654321"):
            self.assertEqual(cl.parse_phones(raw), [("+51987654321", "mobile")], raw)

    def test_lima_landline(self):
        for raw in ("(01) 234-5678", "01 2345678", "+51 1 234 5678", "234 5678"):
            self.assertEqual(cl.parse_phones(raw), [("+5112345678", "landline_lima")], raw)

    def test_multiple_and_ordering(self):
        got = cl.parse_phones("(01) 234-5678, 987654321")
        self.assertEqual(got[0], ("+51987654321", "mobile"))  # mobile first
        self.assertEqual(len(got), 2)

    def test_junk(self):
        self.assertEqual(cl.parse_phones("", "abc", "12345", "000"), [])


class Websites(unittest.TestCase):
    def test_types(self):
        c = cl.classify_website
        self.assertEqual(c("")[0], "none")
        self.assertEqual(c("https://www.instagram.com/clinica")[0], "social")
        self.assertEqual(c("https://linktr.ee/x")[0], "social")
        self.assertEqual(c("https://wa.me/51987654321")[0], "social")
        self.assertEqual(c("https://clinica.business.site")[0], "free_builder")
        self.assertEqual(c("https://doctoralia.pe/x")[0], "directory")
        self.assertEqual(c("https://www.sonrisaperfecta.pe/")[0], "own")
        self.assertEqual(c("sonrisaperfecta.pe")[0], "own")


class District(unittest.TestCase):
    def test_find(self):
        self.assertEqual(cl.find_district("Av. Larco 123, Miraflores 15074, Perú"), "Miraflores")
        self.assertEqual(cl.find_district("Calle X, San Juan de Miraflores, Lima"), "San Juan de Miraflores")
        self.assertEqual(cl.find_district("Jr. Y, Jesús María 15072"), "Jesús María")
        self.assertEqual(cl.find_district("Av. Z, Surco, Lima"), "Santiago de Surco")


def raw(**kw):
    base = dict(place_id="", name="", address="", phone="", phone_international="", website="",
                rating="", reviews="", business_status="OPERATIONAL", closed_flag="", maps_url="",
                category="dentist", types="", district_col="")
    base.update(kw)
    return base


class Pipeline(unittest.TestCase):
    def run_rows(self, rows):
        return cl.process(rows)

    def test_end_to_end(self):
        rows = [
            raw(place_id="a1", name="Clínica Dental Sonrisa Sana", address="Av. Larco 1, Miraflores",
                phone="987654321", rating="4.8", reviews="150"),                       # tier A, no web
            raw(place_id="a1", name="Clinica Dental Sonrisa Sana", address="Av. Larco 1, Miraflores",
                phone="987654321", rating="4.8", reviews="150"),                       # dup place id
            raw(place_id="a2", name="Sonrisa Sana Dental", address="Av. Larco 1, Miraflores",
                phone="+51 987 654 321", rating="4.1", reviews="3"),                   # dup phone, overlapping name
            raw(place_id="b1", name="Odontología Dra. Pérez", address="Calle 2, San Borja",
                phone="(01) 345-6789", website="https://instagram.com/draperez", rating="4.3", reviews="40"),
            raw(place_id="c1", name="Dental Pro Cerrada", address="X, Surco", phone="987000111",
                business_status="CLOSED_PERMANENTLY"),                                 # closed
            raw(place_id="d1", name="Panadería Don José", address="X, Lince", phone="987000222",
                category="bakery"),                                                    # not dental
            raw(place_id="e1", name="Depósito Dental Lima", address="X, Lima", phone="987000333"),  # supplier
            raw(place_id="f1", name="Sanna Clínica Dental", address="X, San Isidro", phone="987000444"),  # institution
            raw(place_id="g1", name="Dental Sin Contacto", address="X, Comas"),        # no channel
            raw(place_id="h1", name="Clínica Dental Moderna", address="Av. Y, La Molina",
                phone="912345678", website="https://www.dentalmoderna.pe", rating="4.9", reviews="300"),  # has own site
        ]
        kept, rejected = self.run_rows(rows)
        names = [r["name"] for r in kept]
        self.assertEqual(len(kept), 3, names)
        reasons = sorted(r["reason"] for r in rejected)
        self.assertEqual(reasons, sorted([
            "duplicate_place_id", "duplicate_phone", "closed", "not_dental",
            "not_a_clinic(supplier/lab/school)", "institution_or_chain", "no_contact_channel"]))

        by_id = {r["place_id"]: r for r in kept}
        a, b, h = by_id["a1"], by_id["b1"], by_id["h1"]
        self.assertEqual(a["tier"], "A")
        self.assertEqual(h["tier"], "C")  # own website caps the tier
        self.assertEqual(a["whatsapp_link"], "https://wa.me/51987654321")
        self.assertEqual(a["district"], "Miraflores")
        self.assertEqual(b["website_type"], "social")
        self.assertTrue(b["social"].startswith("https://instagram.com"))
        self.assertEqual(b["channel"], "instagram/facebook" if b["phone_type"] != "mobile" else "whatsapp")
        self.assertGreater(a["score"], h["score"])  # no website beats has-website at similar reputation
        self.assertIn("su ficha no tiene web", a["personalization_note"])
        # sorted best first
        self.assertEqual(kept[0]["place_id"], "a1")

    def test_cli_roundtrip_with_outscraper_style_headers(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.csv")
            with open(src, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["name", "full_address", "phone", "site", "reviews_rating", "reviews", "type", "google_id"])
                w.writerow(["Clínica Dental Sonrisa", "Av. Pardo 5, Miraflores", "+51 999 111 222", "", "4.7", "88", "Dentist", "g1"])
            out, rej = os.path.join(d, "o.csv"), os.path.join(d, "r.csv")
            self.assertEqual(cl.main([src, "-o", out, "--rejected", rej]), 0)
            with open(out, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["phone"], "+51999111222")
            self.assertEqual(rows[0]["district"], "Miraflores")


class Fetch(unittest.TestCase):
    def test_place_to_row(self):
        p = {"id": "X", "displayName": {"text": "Dental X"}, "formattedAddress": "Addr",
             "nationalPhoneNumber": "987 654 321", "websiteUri": "https://x.pe", "rating": 4.5,
             "userRatingCount": 10, "businessStatus": "OPERATIONAL", "types": ["dentist", "health"],
             "location": {"latitude": -12.1, "longitude": -77.0}}
        row = fp.place_to_row(p, "q")
        self.assertEqual(row["name"], "Dental X")
        self.assertEqual(row["types"], "dentist|health")
        self.assertEqual(set(row), set(fp.RAW_COLUMNS))

    def test_search_request_shape(self):
        captured = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"places": []}'

        def fake_urlopen(req, timeout=0):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["body"] = req.data
            return Resp()

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertEqual(fp.search("KEY", "dentista en Miraflores, Lima, Perú"), {"places": []})
        self.assertEqual(captured["headers"]["x-goog-api-key"], "KEY")
        self.assertIn("places.websiteUri", captured["headers"]["x-goog-fieldmask"])
        self.assertIn(b"PE", captured["body"])

    def test_dry_run_needs_no_key(self):
        self.assertEqual(fp.main(["--dry-run", "--districts", "Miraflores", "--queries", "dentista"]), 0)


if __name__ == "__main__":
    unittest.main()
