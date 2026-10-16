import csv
import os
import tempfile
import unittest
from unittest import mock

import clean_leads as cl
import fetch_places as fp
import fetch_apify as fa
import make_outreach as mo
import send_queue as sq
import scheduled_sender as ss
import sqlite3
from datetime import datetime, timezone, timedelta


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


class Exports(unittest.TestCase):
    """Column mapping for the two most common Maps export tools."""

    def test_apify_style(self):
        rows = [
            {"title": "Dental Apify Uno", "address": "Av. Arequipa 1, Lince", "phone": "+51 987 654 321",
             "website": "", "url": "https://www.google.com/maps/place/x", "totalScore": "4.6",
             "reviewsCount": "55", "categoryName": "Dentist", "placeId": "P1",
             "permanentlyClosed": "false", "temporarilyClosed": "false"},
            {"title": "Dental Apify Cerrado", "address": "Av. Arequipa 2, Lince", "phone": "987000999",
             "url": "https://www.google.com/maps/place/y", "categoryName": "Dentist", "placeId": "P2",
             "permanentlyClosed": "false", "temporarilyClosed": "true"},
        ]
        kept, rejected = cl.process([cl.canon_row(r) for r in rows])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["website_type"], "none")  # Maps link must NOT count as a website
        self.assertEqual(kept[0]["maps_url"], "https://www.google.com/maps/place/x")
        self.assertEqual(kept[0]["place_id"], "P1")
        self.assertEqual([r["reason"] for r in rejected], ["closed"])

    def test_tsv_and_maps_url_from_place_id(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.tsv")
            with open(src, "w", encoding="utf-8") as f:
                f.write("title\taddress\tphoneUnformatted\ttotalScore\treviewsCount\tcategoryName\tplaceId\tpermanentlyClosed\ttemporarilyClosed\n")
                f.write("Dr. Perez, Odontólogo\tAv. Larco 1, Miraflores\t+51987654321\t4.8\t30\tDentista\tPID1\t\t\n")
            rows = cl.read_inputs([src])
            kept, _ = cl.process(rows)
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["name"], "Dr. Perez, Odontólogo")
            self.assertTrue(kept[0]["maps_url"].endswith("place_id:PID1"))

    def test_outscraper_style(self):
        r = cl.canon_row({"name": "D", "full_address": "A, Miraflores", "phone": "987654321", "site": "https://d.pe",
                          "rating": "4.5", "reviews": "20", "type": "Dentist", "google_id": "G1",
                          "location_link": "https://maps/x", "business_status": "OPERATIONAL"})
        self.assertEqual((r["website"], r["rating"], r["reviews"], r["place_id"]), ("https://d.pe", "4.5", "20", "G1"))


class ApifyRunner(unittest.TestCase):
    def test_build_input(self):
        i = fa.build_input("Miraflores", ["dentista"], 40)
        self.assertEqual(i["locationQuery"], "Miraflores, Lima, Perú")
        self.assertEqual((i["language"], i["countryCode"], i["website"]), ("es", "pe", "withoutWebsite"))
        self.assertNotIn("skipClosedPlaces", i)  # paid filter; the cleaner drops closed places for free
        self.assertNotIn("maxReviews", i)  # reviews are the biggest cost driver

    def test_dry_run_and_missing_token(self):
        self.assertEqual(fa.main(["--dry-run"]), 0)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("os.path.exists", return_value=False):
            with self.assertRaises(SystemExit):
                fa.main(["--test"])

    def test_full_flow_with_budget_and_csv_roundtrip(self):
        names = {1: "Sonrisa Alfa", 2: "Odontosalud Beta"}
        item = lambda n, pid: {"title": names[n], "address": "Av. X 1, Miraflores", "phone": f"987 654 32{n}",
                               "phoneUnformatted": f"+5198765432{n}", "website": None, "totalScore": 4.7,
                               "reviewsCount": 50, "categoryName": "Dentist", "categories": ["Dentist", "Clinic"],
                               "placeId": pid, "url": "https://maps/" + pid, "permanentlyClosed": False,
                               "temporarilyClosed": False}
        calls = []

        def fake_api(method, path, token, body=None, params=None):
            calls.append((method, path, params))
            if method == "POST" and path.endswith("/runs"):
                return {"data": {"id": "R", "status": "RUNNING", "defaultDatasetId": "D"}}
            if path.startswith("/actor-runs/"):
                return {"data": {"id": "R", "status": "SUCCEEDED", "defaultDatasetId": "D", "usageTotalUsd": 1.5}}
            return [item(1, "A"), item(2, "B"), item(2, "B")]  # duplicate placeId within run

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"APIFY_TOKEN": "t"}), \
                mock.patch.object(fa, "api", fake_api):
            out = os.path.join(d, "o.csv")
            # budget $2: first run costs $1.5, second would start with only $0.5 cap, third is skipped
            self.assertEqual(fa.main(["--districts", "Miraflores", "San Isidro", "La Molina", "--budget-usd", "2",
                                      "--out", out]), 0)
            starts = [c for c in calls if c[0] == "POST" and c[1].endswith("/runs")]
            self.assertEqual(len(starts), 2)
            self.assertAlmostEqual(starts[1][2]["maxTotalChargeUsd"], 0.5)
            with open(out, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)  # deduped by placeId across runs
            # the cleaner must accept this file as-is and not mistake the Maps url for a website
            kept, _ = cl.process([cl.canon_row(r) for r in rows])
            self.assertEqual(len(kept), 2)
            self.assertEqual(kept[0]["website_type"], "none")
            self.assertEqual(sorted(r["phone"] for r in kept), ["+51987654321", "+51987654322"])

    def test_explain_hints(self):
        self.assertIn("Token", fa.explain(401, '{"error": {"message": "User was not found or authentication token is not valid"}}'))
        self.assertIn("credit", fa.explain(402, '{"error": {"message": "Monthly usage hard limit exceeded"}}'))


class Outreach(unittest.TestCase):
    ROWS = [
        {"tier": "A", "score": "90", "name": "Dental Uno", "district": "San Borja", "phone": "+51987654321",
         "phone_type": "mobile", "rating": "5.0", "reviews": "112", "maps_url": "u1"},
        {"tier": "A", "score": "80", "name": "Dental Fijo", "district": "Miraflores", "phone": "+5112345678",
         "phone_type": "landline_lima", "rating": "", "reviews": "", "maps_url": "u2"},
        {"tier": "B", "score": "60", "name": "Dental Tres", "district": "", "phone": "+51912345678",
         "phone_type": "mobile", "rating": "", "reviews": "", "maps_url": "u3"},
    ]

    def test_select_only_mobile_and_exclude(self):
        self.assertEqual([r["name"] for r in mo.select(self.ROWS, 10)], ["Dental Uno", "Dental Tres"])
        self.assertEqual([r["name"] for r in mo.select(self.ROWS, 10, exclude={"+51987654321"})], ["Dental Tres"])
        self.assertEqual([r["name"] for r in mo.select(self.ROWS, 10, min_reviews=50)], ["Dental Uno"])

    def test_message_and_link(self):
        m = mo.build_message(self.ROWS[0], "Alan", "full")
        self.assertIn("5.0⭐ con 112 reseñas", m)
        self.assertIn("dentista en San Borja", m)
        self.assertIn("no le escriba más", m)  # opt-out line
        self.assertIn("su consultorio en Google", mo.build_message(self.ROWS[2], "Alan", "full"))
        self.assertIn("dentista en Lima", mo.build_message(self.ROWS[2], "Alan", "full"))
        link = mo.wa_link("+51987654321", "hola ñ\n1")
        self.assertTrue(link.startswith("https://wa.me/51987654321?text=hola%20%C3%B1%0A1"))

    def test_short_style_follows_the_checklist(self):
        row = dict(self.ROWS[0], name="Clínica Dental Uno | Ortodoncia | Implantes | Carillas")
        m = mo.build_message(row, "Alan")  # short is the default
        self.assertIn("Soy Alan", m)                       # introduces themself first
        self.assertIn("Clínica Dental Uno en Google (5.0⭐, 112 reseñas)", m)  # specific, short name
        self.assertNotIn("Ortodoncia", m)
        self.assertNotIn("http", m)                        # no link in the first message
        self.assertIn("¿", m)                              # ends in an easy question, not a pitch
        self.assertIn("no le escribo más", m)              # opt-out
        self.assertLess(len(m), 330)                       # short
        self.assertIn("una sola vez más", mo.FOLLOWUP)     # exactly one follow-up
        self.assertNotIn("http", mo.FOLLOWUP)
        self.assertEqual(mo.short_name("A" * 80), "A" * 42 + "…")


class SendQueue(unittest.TestCase):
    def rows(self, n=4):
        return [{"name": f"C{i}", "district": "X", "phone": f"+5198000000{i}", "wa_link": f"https://wa.me/{i}", "sent": ""}
                for i in range(n)]

    def lima(self, h):  # a UTC datetime that is hour h in Lima
        return datetime(2026, 10, 14, h + 5, 0, tzinfo=timezone.utc)

    def test_hours_and_delay(self):
        self.assertTrue(sq.in_hours(self.lima(10), 9, 18))
        self.assertFalse(sq.in_hours(self.lima(8), 9, 18))
        self.assertFalse(sq.in_hours(self.lima(18), 9, 18))
        import random
        d = [sq.delay_seconds(random.Random(i), 4, 9) for i in range(50)]
        self.assertTrue(all(240 <= x <= 540 for x in d))
        self.assertGreater(len(set(d)), 40)  # actually randomized

    def run_queue(self, argv, answers, hour=10, rows=None):
        opened, slept = [], []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "b.csv")
            sq.save(path, rows or self.rows())
            it = iter(answers)
            rc = sq.main(["--batch", path] + argv, now_fn=lambda: self.lima(hour), sleep=slept.append,
                         ask=lambda _: next(it), opener=opened.append)
            return rc, opened, slept, sq.load(path)

    def test_cap_stops_and_pauses_between(self):
        rc, opened, slept, rows = self.run_queue(["--daily-cap", "2"], ["", "", ""])
        self.assertEqual(rc, 0)
        self.assertEqual(len(opened), 2)          # cap respected
        self.assertEqual(len(slept), 2)           # a pause after each send
        self.assertTrue(all(240 <= s <= 540 for s in slept))
        self.assertEqual(sum(1 for r in rows if r["sent"]), 2)

    def test_skip_quit_and_outside_hours(self):
        rc, opened, slept, rows = self.run_queue([], ["s", "q"])
        self.assertEqual(len(opened), 2)
        self.assertTrue(rows[0]["sent"].startswith("skipped"))
        self.assertEqual(rows[1]["sent"], "")     # quit leaves it pending
        self.assertEqual(slept, [])               # no pause after skip/quit
        rc, opened, slept, rows = self.run_queue([], [], hour=7)
        self.assertEqual(opened, [])              # nothing opened outside working hours

    def test_resume_skips_already_sent(self):
        rows = self.rows(3)
        rows[0]["sent"] = self.lima(9).astimezone(sq.LIMA).isoformat(timespec="minutes")
        rc, opened, slept, out = self.run_queue(["--daily-cap", "10"], ["", ""], rows=rows)
        self.assertEqual(opened, ["https://wa.me/1", "https://wa.me/2"])


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

    def test_explain_error_hints(self):
        body = '{"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "Places API (New) has not been used in project 123 before or it is disabled."}}'
        self.assertIn("Enable 'Places API (New)'", fp.explain_error(403, body))
        self.assertIn("billing", fp.explain_error(403, '{"error": {"message": "BILLING_DISABLED"}}').lower())
        self.assertIn("--resume", fp.explain_error(429, '{"error": {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}}'))
        self.assertIn("wrong", fp.explain_error(400, '{"error": {"message": "API key not valid. Please pass a valid API key."}}'))
        self.assertIn("API error 500", fp.explain_error(500, "not json"))

    def test_load_key_env_beats_file(self):
        with mock.patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": " from-env "}):
            self.assertEqual(fp.load_key(), "from-env")
        with mock.patch.dict(os.environ, {}, clear=True):
            fake = mock.mock_open(read_data="# c\nGOOGLE_MAPS_API_KEY='from-file'\n")
            with mock.patch("os.path.exists", return_value=True), mock.patch("builtins.open", fake):
                self.assertEqual(fp.load_key(), "from-file")

    def test_error_midrun_saves_partial_then_resume_continues(self):
        place = lambda i: {"id": f"P{i}", "displayName": {"text": f"Dental {i}"}, "formattedAddress": "x"}
        calls = []

        def flaky(key, q, token=None):
            calls.append(q)
            if len(calls) == 3:  # third request hits the daily quota
                raise fp.ApiError("quota")
            return {"places": [place(len(calls))]}

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "k"}):
            out = os.path.join(d, "raw.csv")
            argv = ["--out", out, "--districts", "A", "B", "C", "--queries", "q", "--sleep", "0"]
            with mock.patch.object(fp, "search", flaky):
                self.assertEqual(fp.main(argv), 1)  # failed run still writes partial data
            with open(out, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)
            calls.clear()
            with mock.patch.object(fp, "search", lambda key, q, token=None: (calls.append(q), {"places": [place(99)]})[1]):
                self.assertEqual(fp.main(argv + ["--resume"]), 0)
            self.assertEqual(calls, ["q en C, Lima, Perú"])  # only the unfinished query re-ran
            with open(out, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 3)

    def test_dry_run_needs_no_key(self):
        self.assertEqual(fp.main(["--dry-run", "--districts", "Miraflores", "--queries", "dentista"]), 0)


class ScheduledSender(unittest.TestCase):
    def lima(self, h, day=14):
        return datetime(2026, 10, day, 0, 0, tzinfo=timezone.utc) + timedelta(hours=h + 5)

    def rows(self, n=3):
        return [{"name": f"C{i}", "district": "X", "phone": f"+5198000000{i}", "message": f"hola {i}",
                 "followup": f"seguimiento {i}", "sent": "", "replied": "", "followup_sent": "", "stop": "", "notes": ""}
                for i in range(n)]

    def run_sender(self, argv, hour=10, rows=None, send=None, db_rows=None, day=14):
        calls = []

        def fake(url, to, text):
            calls.append((to, text))
            return (True, "ok") if send is None else send(to, text)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "b.csv")
            ss.save(path, rows or self.rows())
            extra = []
            if db_rows is not None:
                db = os.path.join(d, "messages.db")
                con = sqlite3.connect(db)
                con.execute("CREATE TABLE messages (id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP, is_from_me BOOLEAN)")
                con.executemany("INSERT INTO messages VALUES (?,?,?,?,?,0)", db_rows)
                con.commit()
                con.close()
                extra = ["--db", db]
            slept = []

            def sleeper(s):
                slept.append(s)
                if len(slept) >= 3:
                    open(os.path.join(d, "STOP"), "w").close()

            rc = ss.main(["--batch", path, "--stop-file", os.path.join(d, "STOP")] + extra + argv,
                         now_fn=lambda: self.lima(hour, day), sleep=sleeper, send=fake)
            return rc, calls, slept, sq.load(path)

    def test_dry_run_sends_nothing(self):
        rc, calls, _, rows = self.run_sender([])
        self.assertEqual((rc, calls), (0, []))
        self.assertEqual(rows[0]["sent"], "")

    def test_live_respects_cap_and_gap(self):
        rc, calls, slept, rows = self.run_sender(["--live", "--daily-cap", "2"])
        self.assertEqual([c[1] for c in calls], ["hola 0", "hola 1"])
        self.assertEqual(calls[0][0], "51980000000")  # digits only, no "+"
        self.assertTrue(all(600 <= s <= 1800 for s in slept[:2]))
        self.assertEqual(rows[2]["sent"], "")

    def test_outside_hours_and_stop_file(self):
        _, calls, _, _ = self.run_sender(["--live", "--once"], hour=19)
        self.assertEqual(calls, [])
        with tempfile.TemporaryDirectory() as d:
            stop = os.path.join(d, "STOP")
            open(stop, "w").close()
            path = os.path.join(d, "b.csv")
            ss.save(path, self.rows())
            sent = []
            ss.main(["--batch", path, "--live", "--stop-file", stop], now_fn=lambda: self.lima(10),
                    send=lambda *a: sent.append(a) or (True, ""))
            self.assertEqual(sent, [])

    def test_three_failures_trip_breaker(self):
        rc, calls, _, rows = self.run_sender(["--live"], send=lambda to, t: (False, "boom"))
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 3)
        self.assertIn("send_fail", rows[0]["notes"])

    def test_require_opt_in(self):
        rows = self.rows()
        for r in rows:
            r["opt_in"] = ""
        rows[1]["opt_in"] = "pidio info"
        _, calls, _, _ = self.run_sender(["--live", "--once", "--require-opt-in"], rows=rows)
        self.assertEqual([c[1] for c in calls], ["hola 1"])

    def test_opt_out_detection(self):
        for t in ["No", "no me escriba más", "No gracias", "Por favor dar de baja", "esto es spam", "no me interesa"]:
            self.assertTrue(ss.is_opt_out(t), t)
        for t in ["Hola, sí me interesa", "¿Cuánto cuesta?", "Buenos días"]:
            self.assertFalse(ss.is_opt_out(t), t)

    def test_reply_sync_marks_replied_and_stop(self):
        rows = self.rows(2)
        rows[0]["sent"] = "2026-10-13T10:00-05:00"
        rows[1]["sent"] = "2026-10-13T10:05-05:00"
        db = [("1", "51980000000@s.whatsapp.net", "x", "Hola, cuánto cuesta?", "2026-10-13 11:00:00-05:00"),
              ("2", "51980000001@s.whatsapp.net", "x", "No me escriba más", "2026-10-13 12:00:00.123456789-05:00")]
        _, calls, _, out = self.run_sender(["--live", "--once", "--followups"], rows=rows, db_rows=db)
        self.assertTrue(out[0]["replied"])
        self.assertEqual(out[0]["stop"], "")
        self.assertTrue(out[1]["stop"].startswith("optout"))
        self.assertEqual(calls, [])  # replied / opted out: nothing more is sent

    def test_followup_once_after_three_days_only_if_silent(self):
        rows = self.rows(3)
        rows[0]["sent"] = "2026-10-10T10:00-05:00"                            # 4 days, silent -> due
        rows[1]["sent"] = "2026-10-10T10:00-05:00"
        rows[1]["replied"] = "x"                                              # replied -> no
        rows[2]["sent"] = "2026-10-13T10:00-05:00"                            # 1 day -> no
        _, calls, _, out = self.run_sender(["--live", "--once", "--followups"], rows=rows)
        self.assertEqual([c[1] for c in calls], ["seguimiento 0"])
        self.assertTrue(out[0]["followup_sent"])
        _, calls2, _, _ = self.run_sender(["--live", "--once", "--followups"], rows=out)
        self.assertNotIn("seguimiento 0", [c[1] for c in calls2])

    def test_test_to(self):
        calls = []
        rc = ss.main(["--test-to", "+54 9 11 5933-9911", "--live"], send=lambda u, to, t: calls.append(to) or (True, ""))
        self.assertEqual((rc, calls), (0, ["5491159339911"]))


class DoctorTests(unittest.TestCase):
    def test_parse_go_version(self):
        import doctor
        self.assertEqual(doctor.parse_go_version("go version go1.22.3 linux/amd64"), (1, 22))
        self.assertEqual(doctor.parse_go_version("go version go1.9 darwin/arm64"), (1, 9))
        self.assertIsNone(doctor.parse_go_version(""))
        self.assertIsNone(doctor.parse_go_version("command not found"))

    def test_summarize_batch(self):
        import doctor
        rows = [{"sent": "x", "replied": "", "stop": "", "opt_in": "", "followup": "f"},
                {"sent": "", "replied": "", "stop": "optout", "opt_in": "", "followup": ""},
                {"sent": "", "replied": "", "stop": "", "opt_in": "pidió info", "followup": "f"}]
        s = doctor.summarize_batch(rows)
        self.assertEqual((s["rows"], s["sent"], s["stop"], s["opt_in"], s["pending"], s["has_followup_text"]),
                         (3, 1, 1, 1, 1, 2))

    def test_bridge_up_false_when_nothing_listens(self):
        import doctor
        self.assertFalse(doctor.bridge_up("http://127.0.0.1:9"))

    def test_bridge_up_true_on_http_answer(self):
        import doctor, threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        t = threading.Thread(target=srv.handle_request)
        t.start()
        try:
            self.assertTrue(doctor.bridge_up(f"http://127.0.0.1:{srv.server_port}"))
        finally:
            t.join()
            srv.server_close()

    def test_main_reports_missing_bridge(self):
        import doctor, io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doctor.main(["--bridge-dir", "/nonexistent/x", "--bridge-url", "http://127.0.0.1:9",
                              "--batch", "/nonexistent/b.csv"])
        self.assertEqual(rc, 1)
        self.assertIn("Pendiente", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
