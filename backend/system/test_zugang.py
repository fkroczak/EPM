"""Zugang (Wunsch 11.10.2026): SSH nur auf Zeit (1, 4, 8 Stunden, danach schließt der Server es selbst), erlaubte Netze
für EPM (HTTPS) und SSH mit Schutz vor dem Aussperren, Netzfilter für EPM (Docker umgeht ufw), Stand von ufw und
Fail2ban. Geprüft: der Systemagent gegen einen nachgebildeten Server (ufw, systemctl, iptables, fail2ban-client – es
wird nichts am echten System geändert), die Endpunkte (Rechte, Prüfungen, Bestätigung, Audit-Log, Adresse des Geräts)
und der Weg Backend → Agent im Probelauf."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone as tz
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, client_fuer

from . import host
from .models import Systemauftrag
from .test_verwaltung import agent_modul
from .tests import AGENT, Systemverzeichnis

KONF = ('EPM_MGMT_IF="enp0s8"\nEPM_MGMT_IP="192.168.56.10"\nEPM_MGMT_NET="192.168.56.0/24"\nEPM_SSH_PORT="2222"\n'
        'EPM_BASE="/srv/epm"\n')


class FalscherServer:
    """Nachbildung der Befehle, die der Agent für den Zugang aufruft – mit Zustand, damit Folgen sichtbar werden."""

    def __init__(self, regeln=None, ssh_aktiv=True):
        self.aufrufe = []
        # (Ziel, Aktion, Von, Kommentar)
        self.regeln = list(regeln if regeln is not None else [
            ("2222/tcp on enp0s8", "ALLOW IN", "192.168.56.0/24", "SSH"),
            ("443/tcp on enp0s8", "ALLOW IN", "192.168.56.0/24", "HTTPS EPM"),
        ])
        self.ssh_aktiv = ssh_aktiv
        self.ketten = {"DOCKER-USER": []}
        self.fehler = set()           # Befehlsanfänge, die fehlschlagen sollen
        self.gesperrt = {"sshd": ["203.0.113.7", "198.51.100.4"]}

    def tabelle(self, nummern):
        zeilen = ["Status: active", "Logging: on (low)", "Default: deny (incoming), allow (outgoing), deny (routed)",
                  "New profiles: skip", "", "     To                         Action      From",
                  "     --                         ------      ----"]
        for i, (ziel, aktion, von, kommentar) in enumerate(self.regeln, 1):
            vorn = f"[{i:2}] " if nummern else ""
            zeilen.append(f"{vorn}{ziel:<27}{aktion:<12}{von:<30}" + (f" # {kommentar}" if kommentar else ""))
        return "\n".join(zeilen) + "\n"

    def __call__(self, args, **kw):
        args = list(args)
        self.aufrufe.append(args)
        for f in self.fehler:
            if args[:len(f)] == list(f):
                return 1, "Fehler (nachgebildet)\n"
        if args[:3] == ["ufw", "status", "numbered"]:
            return 0, self.tabelle(True)
        if args[:3] == ["ufw", "status", "verbose"]:
            return 0, self.tabelle(False)
        if args[:2] == ["ufw", "allow"]:
            von = args[args.index("from") + 1]
            port = args[args.index("port") + 1]
            ziel = f"{port}/tcp" + (f" on {args[args.index('on') + 1]}" if "on" in args else "")
            kommentar = args[args.index("comment") + 1] if "comment" in args else ""
            if any(r[0] == ziel and r[2] == von for r in self.regeln):
                return 0, "Skipping adding existing rule\n"
            self.regeln.append((ziel, "ALLOW IN", von, kommentar))
            return 0, "Rule added\n"
        if args[:3] == ["ufw", "--force", "delete"]:
            del self.regeln[int(args[3]) - 1]
            return 0, "Rule deleted\n"
        if args[:2] == ["systemctl", "is-active"]:
            return (0, "active\n") if self.ssh_aktiv else (3, "inactive\n")
        if args[:3] == ["systemctl", "enable", "--now"]:
            self.ssh_aktiv = True
            return 0, ""
        if args[:3] == ["systemctl", "disable", "--now"]:
            self.ssh_aktiv = False
            return 0, ""
        if args[0] == "iptables":
            return self.iptables(args[2:])
        if args[:2] == ["fail2ban-client", "status"] and len(args) == 2:
            return 0, "Status\n|- Number of jail:\t1\n`- Jail list:\tsshd, recidive\n"
        if args[:2] == ["fail2ban-client", "status"]:
            liste = self.gesperrt.get(args[2], [])
            return 0, (f"Status for the jail: {args[2]}\n|- Filter\n|  |- Currently failed:\t2\n|  |- Total failed:\t9\n"
                       f"`- Actions\n   |- Currently banned:\t{len(liste)}\n   |- Total banned:\t5\n"
                       f"   `- Banned IP list:\t{' '.join(liste)}\n")
        if args[:2] == ["fail2ban-client", "set"]:
            self.gesperrt[args[2]].remove(args[4])
            return 0, "1\n"
        return 0, ""

    def iptables(self, a):
        if a[0] == "-S":
            if a[1] not in self.ketten:
                return 1, "iptables: No chain/target/match by that name.\n"
            return 0, "".join(f"-A {a[1]} {' '.join(r)}\n" for r in self.ketten[a[1]])
        if a[0] == "-N":
            self.ketten.setdefault(a[1], [])
            return 0, ""
        if a[0] == "-F":
            self.ketten[a[1]] = []
            return 0, ""
        if a[0] == "-X":
            self.ketten.pop(a[1], None)
            return 0, ""
        if a[0] == "-A":
            self.ketten[a[1]].append(a[2:])
            return 0, ""
        if a[0] == "-I":
            self.ketten[a[1]].insert(int(a[2]) - 1, a[3:])
            return 0, ""
        if a[0] == "-C":
            return (0, "") if a[2:] in self.ketten.get(a[1], []) else (1, "Bad rule\n")
        if a[0] == "-D":
            self.ketten[a[1]].remove(a[2:])
            return 0, ""
        return 2, "?"


class AgentZugang(SimpleTestCase):
    def setUp(self):
        # Meldungen des Status-Laufs (stderr, auf dem Server im Journal) nicht in die Testausgabe
        self.stderr = contextlib.redirect_stderr(io.StringIO())
        self.stderr.__enter__()
        self.modul = agent_modul()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        self.etc = self.basis / "etc"
        self.etc.mkdir()
        (self.etc / "epm.conf").write_text(KONF)
        lib = self.basis / "lib"
        lib.mkdir()
        (lib / "ssh.socket").write_text("[Socket]\n")
        self.server = FalscherServer()
        self.a = self.agent()

    def tearDown(self):
        self.stderr.__exit__(None, None, None)
        shutil.rmtree(self.basis, ignore_errors=True)

    def agent(self, trocken=False):
        a = self.modul.Agent(str(self.basis), trocken=trocken)
        a.konf_datei = str(self.etc / "epm.conf")
        a.systemd_lib = (str(self.basis / "lib"),)
        a.befehl = self.server
        return a

    def zustand(self):
        return json.loads((self.etc / "zugang.json").read_text())

    def test_netz_pruefen(self):
        """Backend und Agent prüfen gleich."""
        faelle = {
            ("192.168.10.0/24", "https"): "192.168.10.0/24", ("192.168.10.7/24", "https"): "192.168.10.0/24",
            ("10.8.0.5", "ssh"): "10.8.0.5/32", ("10.0.0.0/8", "https"): "10.0.0.0/8",
            ("fd00:1:2::/48", "ssh"): "fd00:1:2::/48", ("2001:db8::/32", "ssh"): "2001:db8::/32",
            ("0.0.0.0/0", "https"): "0.0.0.0/0", ("0.0.0.0/0", "ssh"): None, ("::/0", "https"): None,
            ("::/0", "ssh"): None, ("0.0.0.0/1", "https"): None, ("10.0.0.0/7", "ssh"): None, ("2001:db8::/31", "ssh"): None,
            ("0.0.0.0/8", "ssh"): None, ("127.0.0.0/8", "ssh"): None, ("224.0.0.0/8", "ssh"): None,
            ("fd00::/48", "https"): None, ("192.168.1.0/24; reboot", "ssh"): None, ("", "ssh"): None, (None, "ssh"): None,
            ("192.168.1.0/24", "smtp"): None, ("300.1.1.1", "ssh"): None,
        }
        for (text, dienst), erwartet in faelle.items():
            with self.subTest(text=text, dienst=dienst):
                for pruefen in (self.modul.netz_pruefen, host.netz_pruefen):
                    fehler, netz = pruefen(text, dienst)
                    self.assertEqual(netz, erwartet, fehler)
                    self.assertEqual(fehler is None, erwartet is not None)
        self.assertIsNotNone(self.modul.netz_pruefen(["10.0.0.0/8"], "ssh")[0])
        self.assertEqual(str(self.modul.ip_pruefen("::ffff:192.168.56.20")), "192.168.56.20")
        self.assertIsNone(self.modul.ip_pruefen("192.168.56.20; x"))

    def test_ufw_regeln_lesen(self):
        text = ("Status: active\n\n     To                         Action      From\n     --                         ------      ----\n"
                "[ 1] 2222/tcp on enp0s8         ALLOW IN    192.168.56.0/24            # SSH\n"
                "[ 2] 443/tcp on enp0s8          ALLOW IN    10.8.0.5                   # EPM HTTPS VPN\n"
                "[ 3] OpenSSH                    ALLOW IN    Anywhere\n"
                "[ 4] 2222/tcp (v6) on enp0s8    ALLOW IN    fd00::/64                  # EPM SSH v6\n"
                "[ 5] 25                         DENY OUT    Anywhere (v6)\n")
        r = self.modul.ufw_regeln(text)
        self.assertEqual([(x["nr"], x["port"], x["proto"], x["von"], x["schnittstelle"], x["v6"], x["kommentar"]) for x in r], [
            (1, "2222", "tcp", "192.168.56.0/24", "enp0s8", False, "SSH"), (2, "443", "tcp", "10.8.0.5", "enp0s8", False, "EPM HTTPS VPN"),
            (3, "", "", "Anywhere", "", False, ""), (4, "2222", "tcp", "fd00::/64", "enp0s8", True, "EPM SSH v6"),
            (5, "25", "", "Anywhere", "", True, "")])
        self.assertEqual([self.modul.regel_erlaubt_port(x, 2222) for x in r], [True, False, False, True, False])
        self.assertTrue(self.modul.regel_erlaubt_port(r[2], 22))         # Profil OpenSSH
        self.assertEqual(str(self.modul.regel_netz(r[1])), "10.8.0.5/32")
        self.assertEqual(str(self.modul.regel_netz(r[4])), "::/0")

    def test_ohne_zugang_json_niemand_ausgesperrt(self):
        """Server vor dieser Version: SSH läuft → „dauerhaft offen (Ersteinrichtung)“, Netze aus epm.conf, nichts
        geschrieben, nichts geschlossen."""
        z, gespeichert = self.a.zugang_lesen()
        self.assertFalse(gespeichert)
        self.assertEqual(z["ssh"]["zustand"], "dauerhaft")
        self.assertEqual([e["netz"] for e in z["netze"]["https"]], ["192.168.56.0/24"])
        self.assertEqual([e["netz"] for e in z["netze"]["ssh"]], ["192.168.56.0/24"])
        self.assertIsNone(self.a.ssh_ablauf_pruefen())
        self.assertFalse((self.etc / "zugang.json").exists())
        self.server.ssh_aktiv = False
        self.assertEqual(self.a.zugang_lesen()[0]["ssh"]["zustand"], "geschlossen")
        stand = self.agent().zugang_stand()
        self.assertEqual((stand["gespeichert"], stand["ssh"]["port"], stand["ssh"]["regeln"]), (False, 2222, 1))
        self.assertEqual(stand["firewall"]["standard"], {"eingehend": "deny", "ausgehend": "allow", "weitergeleitet": "deny"})
        self.assertTrue(stand["firewall"]["aktiv"])
        self.assertEqual(len(stand["firewall"]["regeln"]), 2)
        self.assertEqual([(j["name"], j["gesperrt"], j["anzahl"], j["fehlversuche"]) for j in stand["fail2ban"]["jails"]],
                         [("sshd", ["203.0.113.7", "198.51.100.4"], 2, 2), ("recidive", [], 0, 2)])

    def test_ssh_oeffnen_und_schliessen(self):
        z = []
        for stunden in (0, 2, 24, True, "4", None):
            self.assertEqual(self.a.ssh_oeffnen(stunden, "admin", z.append)[0], 2)
        # Probelauf: Befehle nur angezeigt
        rc, text = self.agent(trocken=True).ssh_oeffnen(4, "admin", z.append, simuliert=True)
        self.assertEqual((rc, text), (0, "Probelauf: SSH nicht geöffnet."))
        self.assertIn("(Probelauf) ufw allow in on enp0s8 from 192.168.56.0/24 to any port 2222 proto tcp comment EPM SSH "
                      "Verwaltungsnetz", "".join(z))
        self.assertIn("(Probelauf) systemctl enable --now ssh.socket ssh.service", "".join(z))
        self.assertFalse((self.etc / "zugang.json").exists())
        self.assertEqual([x for x in self.server.aufrufe if x[:2] != ["systemctl", "is-active"]], [])   # nur gelesen
        self.assertEqual(self.a.ssh_oeffnen_befehle(self.a.zugang_lesen()[0]), [
            ["ufw", "allow", "in", "on", "enp0s8", "from", "192.168.56.0/24", "to", "any", "port", "2222", "proto", "tcp",
             "comment", "EPM SSH Verwaltungsnetz"],
            ["systemctl", "enable", "--now", "ssh.socket", "ssh.service"]])
        # echt (nachgebildet): Ende gespeichert
        vorher = datetime.now(tz.utc)
        rc, text = self.a.ssh_oeffnen(4, "admin", z.append)
        self.assertEqual(rc, 0, text)
        s = self.zustand()["ssh"]
        self.assertEqual((s["zustand"], s["von"]), ("offen", "admin"))
        bis = datetime.fromisoformat(s["bis"])
        self.assertAlmostEqual((bis - vorher).total_seconds(), 4 * 3600, delta=5)
        self.assertIn(bis.astimezone().strftime("%H:%M"), text)
        # schließen: alle Regeln für Port 2222 (auch die alte „SSH“ aus 03-security.sh und IPv6), nicht die für 443
        self.server.regeln.append(("2222/tcp (v6) on enp0s8", "ALLOW IN", "fd00::/64", "EPM SSH v6"))
        self.server.regeln.append(("2222/tcp", "LIMIT IN", "Anywhere", ""))
        self.server.aufrufe.clear()
        rc, text = self.a.ssh_schliessen("admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertIn("3 Firewall-Regel(n) entfernt", text)
        loeschen = [x[3] for x in self.server.aufrufe if x[:3] == ["ufw", "--force", "delete"]]
        self.assertEqual(loeschen, sorted(loeschen, reverse=True))      # von hinten
        self.assertEqual([r[3] for r in self.server.regeln], ["HTTPS EPM"])
        self.assertIn(["systemctl", "disable", "--now", "ssh.socket", "ssh.service"], self.server.aufrufe)
        self.assertEqual(self.zustand()["ssh"]["zustand"], "geschlossen")
        # mehrfach: nichts mehr zu tun, kein Fehler
        self.assertEqual(self.a.ssh_schliessen("admin", z.append)[0], 0)
        # ohne ssh.socket (Ubuntu 22.04): nur ssh.service
        a = self.agent()
        a.systemd_lib = (str(self.basis / "fehlt"),)
        self.assertEqual(a.ssh_einheiten(), ["ssh.service"])
        # kein Netz für SSH: nicht öffnen
        zustand = self.zustand()
        zustand["netze"]["ssh"] = []
        (self.etc / "zugang.json").write_text(json.dumps(zustand))
        self.assertIn("kein Netz für SSH", self.a.ssh_oeffnen(1, "admin", z.append)[1])

    def test_ablauf(self):
        z = []
        self.a.ssh_oeffnen(1, "admin", z.append)
        self.assertIsNone(self.a.ssh_ablauf_pruefen())                    # noch nicht abgelaufen
        spaeter = datetime.now(tz.utc) + timedelta(hours=1, minutes=1)
        self.assertIsNone(self.agent(trocken=True).ssh_ablauf_pruefen(spaeter))   # Probelauf: nie
        # Schließen schlägt fehl: Zustand bleibt „offen“, ein Fehler-Ereignis, der nächste Lauf versucht es erneut
        self.server.fehler.add(("systemctl", "disable"))
        self.assertEqual(self.a.ssh_ablauf_pruefen(spaeter)[0], 1)
        self.assertEqual(self.a.ssh_ablauf_pruefen(spaeter)[0], 1)
        self.assertEqual(self.zustand()["ssh"]["zustand"], "offen")
        self.assertEqual([e["ok"] for e in self.zustand()["ereignisse"]], [False])
        self.server.fehler.clear()
        rc, text = self.a.ssh_ablauf_pruefen(spaeter)
        self.assertEqual(rc, 0, text)
        zustand = self.zustand()
        self.assertEqual((zustand["ssh"]["zustand"], zustand["ssh"]["von"]), ("geschlossen", "automatisch"))
        self.assertEqual([e["ok"] for e in zustand["ereignisse"]], [False, True])
        self.assertFalse(self.server.ssh_aktiv)
        self.assertFalse(any(self.modul.regel_erlaubt_port(r, 2222) for r in self.modul.ufw_regeln(self.server.tabelle(True))))
        self.assertIsNone(self.a.ssh_ablauf_pruefen(spaeter))             # geschlossen: nichts mehr
        # „dauerhaft“ läuft nie ab
        zustand["ssh"] = {"zustand": "dauerhaft", "bis": None}
        (self.etc / "zugang.json").write_text(json.dumps(zustand))
        self.assertIsNone(self.a.ssh_ablauf_pruefen(spaeter + timedelta(days=400)))

    def test_netze_und_schutz_vor_dem_aussperren(self):
        z = []
        hinzu = self.a.netz_hinzufuegen
        self.assertEqual(hinzu({"dienst": "https", "netz": "0.0.0.0/0", "bezeichnung": "alles"}, "admin", z.append)[0], 2)
        self.assertEqual(hinzu({"dienst": "https", "netz": "10.8.0.0/24", "bezeichnung": "VPN'; rm"}, "admin", z.append)[0], 2)
        self.assertEqual(hinzu({"dienst": "dns", "netz": "10.8.0.0/24", "bezeichnung": "VPN"}, "admin", z.append)[0], 2)
        self.assertEqual(hinzu({"dienst": "https", "netz": "192.168.56.0/24", "bezeichnung": "doppelt"}, "admin", z.append)[0], 2)
        rc, text = hinzu({"dienst": "https", "netz": "10.8.0.7/24", "bezeichnung": "VPN Büro"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertIn(("443/tcp on enp0s8", "ALLOW IN", "10.8.0.0/24", "EPM HTTPS VPN Buero"), self.server.regeln)
        self.assertEqual([(e["netz"], e["bezeichnung"]) for e in self.zustand()["netze"]["https"]],
                         [("192.168.56.0/24", "Verwaltungsnetz"), ("10.8.0.0/24", "VPN Büro")])
        # SSH-Netz bei offenem SSH sofort in ufw; bei geschlossenem erst beim nächsten Öffnen
        rc, text = hinzu({"dienst": "ssh", "netz": "fd00:1::/64", "bezeichnung": "IPv6"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertIn(("2222/tcp on enp0s8", "ALLOW IN", "fd00:1::/64", "EPM SSH IPv6"), self.server.regeln)
        self.a.ssh_schliessen("admin", z.append)
        anzahl = len(self.server.regeln)
        rc, text = hinzu({"dienst": "ssh", "netz": "10.9.0.0/16", "bezeichnung": "Praxisnetz 2"}, "admin", z.append)
        self.assertIn("nächsten Öffnen", text)
        self.assertEqual(len(self.server.regeln), anzahl)
        # höchstens 20 je Dienst
        for i in range(17):
            self.assertEqual(hinzu({"dienst": "ssh", "netz": f"172.16.{i}.0/24", "bezeichnung": f"N{i}"}, "admin", z.append)[0], 0)
        self.assertIn("schon 20", hinzu({"dienst": "ssh", "netz": "172.17.0.0/24", "bezeichnung": "zu viel"}, "admin", z.append)[1])
        # Entfernen (HTTPS): ohne Adresse des Geräts nicht; nicht das eigene Netz; nicht das letzte
        weg = self.a.netz_entfernen
        self.assertEqual(weg({"dienst": "https", "netz": "10.8.0.0/24"}, "admin", z.append)[0], 2)
        rc, text = weg({"dienst": "https", "netz": "10.8.0.0/24", "client_ip": "10.8.0.20"}, "admin", z.append)
        self.assertEqual(rc, 2)
        self.assertIn("Ihr Gerät (10.8.0.20)", text)
        self.assertEqual(weg({"dienst": "https", "netz": "10.9.9.0/24", "client_ip": "192.168.56.20"}, "admin", z.append)[0], 2)
        # Probelauf ändert nichts
        self.assertEqual(self.agent(trocken=True).netz_entfernen({"dienst": "https", "netz": "10.8.0.0/24",
                                                                  "client_ip": "192.168.56.20"}, "admin", z.append,
                                                                 simuliert=True)[0], 0)
        self.assertEqual(len(self.zustand()["netze"]["https"]), 2)
        rc, text = weg({"dienst": "https", "netz": "10.8.0.0/24", "client_ip": "192.168.56.20"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertNotIn("10.8.0.0/24", [r[2] for r in self.server.regeln])
        self.assertIn(("443/tcp on enp0s8", "ALLOW IN", "192.168.56.0/24", "HTTPS EPM"), self.server.regeln)
        rc, text = weg({"dienst": "https", "netz": "192.168.56.0/24", "client_ip": "10.1.1.1"}, "admin", z.append)
        self.assertIn("letzte Netz", text)
        # überlappende Netze: das eigene darf weg, wenn ein anderes das Gerät weiter erlaubt
        hinzu({"dienst": "https", "netz": "192.168.0.0/16", "bezeichnung": "Haus"}, "admin", z.append)
        rc, text = weg({"dienst": "https", "netz": "192.168.56.0/24", "client_ip": "192.168.56.20"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        # SSH-Netz entfernen braucht keine Adresse; das letzte darf weg (SSH öffnet dann nicht)
        rc, text = weg({"dienst": "ssh", "netz": "10.9.0.0/16"}, "admin", z.append)
        self.assertEqual(rc, 0, text)

    def test_aus_dem_internet_und_eigene_adresse(self):
        """Nachtrag 11.10.2026: EPM aus dem Internet nur ausdrücklich (0.0.0.0/0, nie für SSH); SSH nur von der eigenen
        Adresse, befristet für diese Öffnung."""
        z = []
        hinzu = self.a.netz_hinzufuegen
        p = {"dienst": "https", "netz": "0.0.0.0/0", "bezeichnung": "Internet (alle Adressen)"}
        self.assertIn("ausdrücklicher Bestätigung", hinzu(p, "admin", z.append)[1])
        self.assertEqual(hinzu({**p, "dienst": "ssh", "internet": True}, "admin", z.append)[0], 2)
        rc, text = hinzu({**p, "internet": True}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertIn(("443/tcp on enp0s8", "ALLOW IN", "0.0.0.0/0", "EPM HTTPS Internet (alle Adressen)"), self.server.regeln)
        stand = self.a.zugang_stand()
        self.assertEqual(stand["internet"], {"alle": True, "oeffentlich": []})
        # das Verwaltungsnetz darf weg (das Gerät im Internet bleibt über 0.0.0.0/0 erlaubt), 0.0.0.0/0 dann nicht mehr
        weg = self.a.netz_entfernen
        self.assertEqual(weg({"dienst": "https", "netz": "192.168.56.0/24", "client_ip": "93.184.216.34"}, "admin", z.append)[0], 0)
        self.assertEqual(weg({"dienst": "https", "netz": "0.0.0.0/0", "client_ip": "93.184.216.34"}, "admin", z.append)[0], 2)
        hinzu({"dienst": "https", "netz": "93.184.216.34", "bezeichnung": "Admin zu Hause"}, "admin", z.append)
        self.assertEqual(self.a.zugang_stand()["internet"]["oeffentlich"], ["93.184.216.34/32"])
        rc, text = weg({"dienst": "https", "netz": "0.0.0.0/0", "client_ip": "93.184.216.34"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertEqual(weg({"dienst": "https", "netz": "93.184.216.34/32", "client_ip": "93.184.216.34"}, "admin",
                             z.append)[0], 2)
        # SSH nur von der eigenen Adresse: andere SSH-Freigaben gehen zu, der Eintrag fällt beim Schließen weg
        self.assertEqual(self.a.ssh_oeffnen(1, "admin", z.append, nur_ip="0.0.0.0/0")[0], 2)
        self.assertEqual(self.a.ssh_oeffnen(1, "admin", z.append, nur_ip="93.184.216.0/24")[0], 2)
        rc, text = self.a.ssh_oeffnen(1, "admin", z.append, nur_ip="93.184.216.34/32")
        self.assertEqual(rc, 0, text)
        ssh = [r for r in self.server.regeln if r[0].startswith("2222/")]
        self.assertEqual([r[2] for r in ssh], ["93.184.216.34/32"])
        self.assertEqual([(e["netz"], e.get("befristet")) for e in self.zustand()["netze"]["ssh"]],
                         [("192.168.56.0/24", None), ("93.184.216.34/32", True)])
        self.assertEqual(self.a.ssh_schliessen("admin", z.append)[0], 0)
        self.assertEqual([e["netz"] for e in self.zustand()["netze"]["ssh"]], ["192.168.56.0/24"])

    def test_netzfilter_fuer_epm(self):
        z = []
        schalten = self.a.https_filter_schalten
        self.assertEqual(schalten({"an": "ja"}, "admin", z.append)[0], 2)
        self.assertEqual(schalten({"an": True}, "admin", z.append)[0], 2)                       # ohne Adresse
        rc, text = schalten({"an": True, "client_ip": "10.50.0.3"}, "admin", z.append)
        self.assertEqual(rc, 2)
        self.assertIn("aussperren", text)
        self.assertEqual(self.server.ketten, {"DOCKER-USER": []})
        rc, text = schalten({"an": True, "client_ip": "192.168.56.20"}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        sprung = ["-p", "tcp", "-m", "conntrack", "--ctorigdst", "192.168.56.10", "--ctorigdstport", "443", "--ctdir",
                  "ORIGINAL", "-j", "EPM-HTTPS"]
        self.assertEqual(self.server.ketten["DOCKER-USER"], [sprung])
        self.assertEqual(self.server.ketten["EPM-HTTPS"], [["-s", "10.231.0.0/24", "-j", "RETURN"],
                                                           ["-s", "10.231.16.0/20", "-j", "RETURN"],
                                                           ["-s", "192.168.56.0/24", "-j", "RETURN"], ["-j", "DROP"]])
        self.assertTrue(self.a.https_filter_aktiv())
        self.assertTrue(self.zustand()["https_filter"])
        # ein neues Netz kommt in die Kette
        self.a.netz_hinzufuegen({"dienst": "https", "netz": "10.8.0.0/24", "bezeichnung": "VPN"}, "admin", z.append)
        self.assertIn(["-s", "10.8.0.0/24", "-j", "RETURN"], self.server.ketten["EPM-HTTPS"])
        self.assertEqual(self.server.ketten["EPM-HTTPS"][-1], ["-j", "DROP"])
        # nach einem Neustart fehlt die Kette: der Status-Lauf hängt sie wieder ein
        self.server.ketten = {"DOCKER-USER": []}
        self.a.https_filter_pruefen()
        self.assertTrue(self.a.https_filter_aktiv())
        # schlägt ein Erlauben fehl, wird nichts verworfen (lieber offen als ausgesperrt)
        self.server.ketten = {"DOCKER-USER": []}
        self.server.fehler.add(("iptables", "-w", "-A", "EPM-HTTPS", "-s", "192.168.56.0/24"))
        self.assertGreater(self.a.https_filter_anwenden(self.a.zugang_lesen()[0], z.append), 0)
        self.assertNotIn(["-j", "DROP"], self.server.ketten["EPM-HTTPS"])
        self.server.fehler.clear()
        # aus: Sprung und Kette weg
        rc, text = schalten({"an": False}, "admin", z.append)
        self.assertEqual(rc, 0, text)
        self.assertEqual(self.server.ketten, {"DOCKER-USER": []})
        self.assertFalse(self.zustand()["https_filter"])

    def test_fail2ban_entsperren(self):
        z = []
        frei = self.a.fail2ban_entsperren
        self.assertEqual(frei("sshd; reboot", "203.0.113.7", z.append)[0], 2)
        self.assertEqual(frei("sshd", "203.0.113.7 || x", z.append)[0], 2)
        self.assertEqual(frei("gibtsnicht", "203.0.113.7", z.append)[0], 2)
        self.assertEqual(frei("sshd", "203.0.113.7", z.append, simuliert=True), (0, "Probelauf: Adresse nicht freigegeben."))
        self.assertEqual(self.server.gesperrt["sshd"], ["203.0.113.7", "198.51.100.4"])
        rc, text = frei("sshd", "203.0.113.7", z.append)
        self.assertEqual(rc, 0, text)
        self.assertIn(["fail2ban-client", "set", "sshd", "unbanip", "203.0.113.7"], self.server.aufrufe)
        self.assertEqual(self.server.gesperrt["sshd"], ["198.51.100.4"])
        self.assertIn("nicht (mehr) gesperrt", frei("sshd", "203.0.113.7", z.append)[1])

    def test_ersteinrichtung(self):
        """rollout/03-security.sh nach „ufw --force reset“: Liste für EPM gilt, SSH dauerhaft offen, Netzfilter auf einem
        neuen Server an; ein erneuter Lauf verliert keine Netze."""
        self.server.regeln.append(("443/tcp", "ALLOW IN", "Anywhere", ""))
        z = []
        self.assertEqual(self.a.zugang_anwenden(True, z.append), 0, "".join(z))
        zustand = self.zustand()
        self.assertEqual((zustand["ssh"]["zustand"], zustand["https_filter"]), ("dauerhaft", True))
        self.assertNotIn(("443/tcp", "ALLOW IN", "Anywhere", ""), self.server.regeln)
        self.assertTrue(self.a.https_filter_aktiv())
        # Netze aus EPM; erneuter Lauf (wie nach ufw --force reset): sie kommen wieder
        self.a.netz_hinzufuegen({"dienst": "https", "netz": "10.8.0.0/24", "bezeichnung": "VPN"}, "admin", z.append)
        self.a.ssh_schliessen("admin", z.append)
        self.server.regeln = [("2222/tcp on enp0s8", "ALLOW IN", "192.168.56.0/24", "SSH"),
                              ("443/tcp on enp0s8", "ALLOW IN", "192.168.56.0/24", "HTTPS EPM")]
        self.assertEqual(self.a.zugang_anwenden(True, z.append), 0, "".join(z))
        self.assertIn(("443/tcp on enp0s8", "ALLOW IN", "10.8.0.0/24", "EPM HTTPS VPN"), self.server.regeln)
        self.assertEqual(self.zustand()["ssh"]["zustand"], "dauerhaft")
        # bestehendes EPM (.env da), noch keine zugang.json: Netzfilter bleibt aus (niemand wird ausgesperrt)
        (self.etc / "zugang.json").unlink()
        (self.basis / ".env").write_text("EPM_VERSION=1\n")
        self.server.ketten = {"DOCKER-USER": []}
        self.assertEqual(self.a.zugang_anwenden(True, z.append), 0)
        self.assertFalse(self.zustand()["https_filter"])
        self.assertFalse(self.a.https_filter_aktiv())


def zugang_status(**extra):
    z = {"gespeichert": True, "stunden": [1, 4, 8], "max": 20,
         "ssh": {"zustand": "geschlossen", "bis": None, "port": 22, "dienst_aktiv": False, "regeln": 0},
         "netze": {"https": [{"netz": "192.168.56.0/24", "bezeichnung": "Verwaltungsnetz"},
                             {"netz": "10.8.0.0/24", "bezeichnung": "VPN"}],
                   "ssh": [{"netz": "192.168.56.0/24", "bezeichnung": "Verwaltungsnetz"}]},
         "https_filter": {"an": False, "aktiv": False, "moeglich": True}, "ereignisse": [],
         "firewall": {"verfuegbar": True, "aktiv": True, "standard": {}, "regeln": []},
         "fail2ban": {"verfuegbar": True, "jails": [{"name": "sshd", "gesperrt": ["203.0.113.7"], "anzahl": 1}]}}
    z.update(extra)
    return z


class ZugangApi(Systemverzeichnis):
    def status(self, **extra):
        daten = {"zeit": timezone.now().isoformat(), "rechner": "epm", "trocken": True, "zugang": zugang_status(**extra)}
        (self.ordner / "status" / "system.json").write_text(json.dumps(daten))

    def auftragsdatei(self):
        dateien = list((self.ordner / "auftraege").glob("*.json"))
        self.assertEqual(len(dateien), 1, dateien)
        return json.loads(dateien[0].read_text())

    def texte(self):
        return [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]

    URLS = ("/api/system/zugang/ssh/oeffnen/", "/api/system/zugang/ssh/schliessen/", "/api/system/zugang/netze/",
            "/api/system/zugang/netze/entfernen/", "/api/system/zugang/filter/", "/api/system/zugang/entsperren/")

    def test_rechte(self):
        self.status()
        for user in (self.mediziner, self.mitarbeiter, self.betrachter):
            c = client_fuer(user)
            for url in self.URLS:
                with self.subTest(benutzer=user.username, url=url):
                    self.assertEqual(c.post(url, {"stunden": 1}, format="json").status_code, 403)
        self.assertEqual(self.auftragsdateien(), [])
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertEqual({k: d["verwaltung"][k]["bestaetigung"] for k in (
            "ssh_oeffnen", "ssh_schliessen", "netz_hinzufuegen", "netz_entfernen", "https_filter", "fail2ban_entsperren")},
            {"ssh_oeffnen": "2fa", "ssh_schliessen": "einfach", "netz_hinzufuegen": "2fa", "netz_entfernen": "2fa",
             "https_filter": "2fa", "fail2ban_entsperren": "einfach"})
        self.assertEqual(d["host"]["zugang"]["ssh"]["zustand"], "geschlossen")

    def test_ssh_oeffnen_und_schliessen(self):
        self.status()
        url = "/api/system/zugang/ssh/oeffnen/"
        b = {"kennwort": KENNWORT, "code": self.admin_codes[0]}
        for stunden in (0, 2, 24, "4", True, None):
            with self.subTest(stunden=stunden):
                r = self.a.post(url, {**b, "stunden": stunden}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn("stunden", r.json())
        # ohne Passwort und Code kein Auftrag
        r = self.a.post(url, {"stunden": 4}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        self.assertEqual(self.auftragsdateien(), [])
        r = self.a.post(url, {"stunden": 4, "kennwort": KENNWORT, "code": "000000"}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["code"]))
        self.drosselung_aufheben()
        r = self.a.post(url, {**b, "stunden": 4}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((self.auftragsdatei()["aktion"], self.auftragsdatei()["parameter"]), ("ssh_oeffnen", {"stunden": 4}))
        self.assertIn("SSH für 4 Stunde(n) öffnen angefordert, mit Passwort und 2FA bestätigt", self.texte())
        # nicht doppelt
        self.assertEqual(self.a.post(url, {"stunden": 1, "kennwort": KENNWORT, "code": self.admin_codes[1]},
                                     format="json").status_code, 409)
        # schließen: einfache Rückfrage
        r = self.a.post("/api/system/zugang/ssh/schliessen/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("SSH schließen angefordert", self.texte())
        # ohne Netz für SSH: gar nicht erst beauftragen
        Systemauftrag.objects.all().delete()
        self.status(netze={"https": [{"netz": "192.168.56.0/24", "bezeichnung": "x"}], "ssh": []})
        r = self.a.post(url, {"stunden": 1, "kennwort": KENNWORT, "code": self.admin_codes[2]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("kein Netz für SSH", r.json()["stunden"])

    def test_netz_hinzufuegen(self):
        self.status()
        url = "/api/system/zugang/netze/"
        b = {"kennwort": KENNWORT, "code": self.admin_codes[0]}
        for daten, feld in (({"dienst": "smtp", "netz": "10.1.0.0/16", "bezeichnung": "x"}, "dienst"),
                            ({"dienst": "https", "netz": "0.0.0.0/0", "bezeichnung": "alles"}, "netz"),
                            ({"dienst": "ssh", "netz": "::/0", "bezeichnung": "alles"}, "netz"),
                            ({"dienst": "ssh", "netz": "10.0.0.0/7", "bezeichnung": "groß"}, "netz"),
                            ({"dienst": "https", "netz": "fd00::/64", "bezeichnung": "v6"}, "netz"),
                            ({"dienst": "https", "netz": "10.1.0.0/16 -j ACCEPT", "bezeichnung": "x"}, "netz"),
                            ({"dienst": "https", "netz": "10.8.0.0/24", "bezeichnung": "doppelt"}, "netz"),
                            ({"dienst": "https", "netz": "10.1.0.0/16", "bezeichnung": ""}, "bezeichnung"),
                            ({"dienst": "https", "netz": "10.1.0.0/16", "bezeichnung": "a\"; ufw disable"}, "bezeichnung"),
                            ({"dienst": "https", "netz": "10.1.0.0/16", "bezeichnung": "x" * 41}, "bezeichnung")):
            with self.subTest(daten=daten):
                r = self.a.post(url, {**b, **daten}, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        self.status(netze={"https": [{"netz": f"10.{i}.0.0/16", "bezeichnung": "x"} for i in range(20)], "ssh": []})
        r = self.a.post(url, {**b, "dienst": "https", "netz": "10.99.0.0/16", "bezeichnung": "zu viel"}, format="json")
        self.assertIn("schon 20", r.json()["netz"])
        self.status()
        r = self.a.post(url, {"dienst": "ssh", "netz": "10.9.0.0/16", "bezeichnung": "Praxisnetz 2"}, format="json")
        self.assertEqual(list(r.json()), ["kennwort"])
        r = self.a.post(url, {**b, "dienst": "ssh", "netz": "10.9.1.2/16", "bezeichnung": " Praxisnetz 2 "}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"dienst": "ssh", "netz": "10.9.0.0/16", "bezeichnung": "Praxisnetz 2"})
        self.assertIn("Erlaubtes Netz für SSH hinzufügen angefordert: 10.9.0.0/16 („Praxisnetz 2“), mit Passwort und 2FA "
                      "bestätigt", self.texte())

    def test_netz_entfernen_schuetzt_vor_dem_aussperren(self):
        url = "/api/system/zugang/netze/entfernen/"
        # der Agent meldet sich nicht: nichts beauftragen
        r = self.a.post(url, {"dienst": "https", "netz": "10.8.0.0/24", "kennwort": KENNWORT, "code": self.admin_codes[0]},
                        format="json")
        self.assertEqual(r.status_code, 409)
        self.status()

        def entfernen(netz, ip, dienst="https", code=1):
            return self.a.post(url, {"dienst": dienst, "netz": netz, "kennwort": KENNWORT, "code": self.admin_codes[code]},
                               format="json", REMOTE_ADDR=ip)

        r = entfernen("10.8.0.0/24", "10.8.0.20")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Ihr Gerät (10.8.0.20)", r.json()["netz"])
        # Nginx gibt die Adresse über X-Real-IP weiter (audit.models.client_ip)
        r = self.a.post(url, {"dienst": "https", "netz": "192.168.56.0/24", "kennwort": KENNWORT,
                              "code": self.admin_codes[1]}, format="json", HTTP_X_REAL_IP="192.168.56.30")
        self.assertIn("Ihr Gerät (192.168.56.30)", r.json()["netz"])
        self.assertIn("nicht eingetragen", entfernen("10.9.0.0/24", "192.168.56.30").json()["netz"])
        self.assertEqual(self.auftragsdateien(), [])
        r = entfernen("10.8.0.0/24", "192.168.56.30")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"dienst": "https", "netz": "10.8.0.0/24",
                                                             "client_ip": "192.168.56.30"})
        self.assertIn("Erlaubtes Netz für EPM (HTTPS) entfernen angefordert: 10.8.0.0/24 („VPN“), mit Passwort und 2FA "
                      "bestätigt", self.texte())
        Systemauftrag.objects.all().delete()
        for p in (self.ordner / "auftraege").glob("*.json"):
            p.unlink()
        self.status(netze={"https": [{"netz": "192.168.56.0/24", "bezeichnung": "x"}],
                           "ssh": [{"netz": "192.168.56.0/24", "bezeichnung": "x"}]})
        self.assertIn("letzte Netz", entfernen("192.168.56.0/24", "10.1.1.1", code=2).json()["netz"])
        # SSH: ohne Adresse des Geräts
        r = entfernen("192.168.56.0/24", "192.168.56.30", dienst="ssh", code=3)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"dienst": "ssh", "netz": "192.168.56.0/24"})

    def test_internet_und_eigene_adresse(self):
        self.status()
        b = {"kennwort": KENNWORT, "code": self.admin_codes[0]}
        url = "/api/system/zugang/netze/"
        r = self.a.post(url, {**b, "dienst": "https", "netz": "0.0.0.0/0", "bezeichnung": "Internet"}, format="json")
        self.assertIn("ausdrücklich", r.json()["netz"])
        for dienst, netz in (("ssh", "0.0.0.0/0"), ("ssh", "::/0"), ("https", "::/0")):
            r = self.a.post(url, {**b, "dienst": dienst, "netz": netz, "bezeichnung": "x", "internet": True}, format="json")
            self.assertEqual(r.status_code, 400, (dienst, netz))
        r = self.a.post(url, {**b, "dienst": "https", "netz": "0.0.0.0/0", "bezeichnung": "Internet", "internet": True},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"]["internet"], True)
        self.assertIn("Erlaubtes Netz für EPM (HTTPS) hinzufügen angefordert: 0.0.0.0/0 („Internet“) – EPM aus dem ganzen "
                      "Internet erreichbar, mit Passwort und 2FA bestätigt", self.texte())
        Systemauftrag.objects.all().delete()
        for p in (self.ordner / "auftraege").glob("*.json"):
            p.unlink()
        # eigene Adresse (wie Nginx sie weitergibt) für SSH
        self.assertEqual(self.a.post(url, {**b, "dienst": "https", "eigene_adresse": True, "bezeichnung": "x"},
                                     format="json").status_code, 400)
        r = self.a.post(url, {"dienst": "ssh", "eigene_adresse": True, "netz": "10.0.0.0/8", "bezeichnung": "Admin admin",
                              "kennwort": KENNWORT, "code": self.admin_codes[1]}, format="json", HTTP_X_REAL_IP="198.51.100.20")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"]["netz"], "198.51.100.20/32")
        Systemauftrag.objects.all().delete()
        for p in (self.ordner / "auftraege").glob("*.json"):
            p.unlink()
        r = self.a.post("/api/system/zugang/ssh/oeffnen/", {"stunden": 1, "nur_eigene_adresse": True, "kennwort": KENNWORT,
                                                            "code": self.admin_codes[2]}, format="json",
                        REMOTE_ADDR="2001:db8::7")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"stunden": 1, "nur_ip": "2001:db8::7/128"})
        self.assertIn("SSH für 1 Stunde(n) öffnen angefordert, nur von 2001:db8::7/128 (nur diese Öffnung)", self.texte()[0])

    def test_netzfilter_und_entsperren(self):
        self.status()
        url = "/api/system/zugang/filter/"
        r = self.a.post(url, {"an": True, "kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json",
                        REMOTE_ADDR="172.20.0.5")
        self.assertIn("aussperren", r.json()["an"])
        self.assertEqual(self.a.post(url, {"an": "ja"}, format="json").status_code, 400)
        r = self.a.post(url, {"an": True, "kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json",
                        REMOTE_ADDR="10.8.0.9")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"an": True, "client_ip": "10.8.0.9"})
        self.assertIn("Netzfilter für EPM einschalten angefordert, mit Passwort und 2FA bestätigt", self.texte())
        # Fail2ban: nur gemeldete Jails, gültige Adressen; einfache Rückfrage
        url = "/api/system/zugang/entsperren/"
        for daten, feld in (({"jail": "sshd; reboot", "ip": "203.0.113.7"}, "jail"), ({"jail": "apache", "ip": "203.0.113.7"}, "jail"),
                            ({"jail": "sshd", "ip": "203.0.113.7 -x"}, "ip"), ({"jail": "sshd", "ip": None}, "ip")):
            with self.subTest(daten=daten):
                r = self.a.post(url, daten, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(feld, r.json())
        r = self.a.post(url, {"jail": "sshd", "ip": "203.0.113.7"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("Gesperrte Adresse 203.0.113.7 freigeben angefordert (Fail2ban, Jail sshd)", self.texte())

    def test_automatisch_geschlossen_im_audit_log(self):
        e = {"id": "a1b2c3d4e5f60718", "zeit": timezone.now().isoformat(), "art": "abgelaufen", "ok": True,
             "bis": timezone.now().isoformat(), "text": "SSH ist geschlossen (2 Firewall-Regel(n) entfernt, Dienst aus)."}
        self.status(ereignisse=[e, {"id": "../x"}])
        self.a.get("/api/system/uebersicht/")
        self.a.get("/api/system/uebersicht/")
        liste = SystemEreignis.objects.filter(details__ereignis="ssh_automatisch")
        self.assertEqual(liste.count(), 1)
        self.assertEqual(liste[0].benutzername, "systemagent")
        self.assertIn("SSH nach Ablauf der Zeit vom Server geschlossen: SSH ist geschlossen (2 Firewall-Regel(n) entfernt, "
                      "Dienst aus).", self.texte())

    def test_echter_agent_im_probelauf(self):
        """Backend legt ab → Agent (Probelauf, eigene epm.conf) → Ergebnis: nichts verändert."""
        self.status()
        self.a.post("/api/system/zugang/ssh/oeffnen/", {"stunden": 8, "kennwort": KENNWORT, "code": self.admin_codes[0]},
                    format="json")
        self.a.post("/api/system/zugang/entsperren/", {"jail": "sshd", "ip": "203.0.113.7"}, format="json")
        self.a.post("/api/system/zugang/netze/", {"dienst": "https", "netz": "10.20.0.0/16", "bezeichnung": "Praxis",
                                                  "kennwort": KENNWORT, "code": self.admin_codes[1]}, format="json")
        self.assertEqual(len(self.auftragsdateien()), 3)
        basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        try:
            os.symlink(self.ordner, basis / "system")
            (basis / "epm.conf").write_text(KONF)
            p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(basis), "--trocken",
                                "--einstellungen", str(basis / "epm.conf")], capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse((basis / "zugang.json").exists())
        finally:
            shutil.rmtree(basis, ignore_errors=True)
        self.a.get("/api/system/auftraege/")
        ergebnisse = {a.aktion: (a.status, a.ergebnis, a.probelauf) for a in Systemauftrag.objects.all()}
        self.assertEqual(ergebnisse, {
            "ssh_oeffnen": ("erledigt", "Probelauf: SSH nicht geöffnet.", True),
            "fail2ban_entsperren": ("erledigt", "Probelauf: Adresse nicht freigegeben.", True),
            "netz_hinzufuegen": ("erledigt", "Probelauf: Netz nicht eingetragen.", True)})
        a = Systemauftrag.objects.get(aktion="ssh_oeffnen")
        self.assertTrue(re.search(r"\(Probelauf\) ufw allow in on enp0s8 from 192\.168\.56\.0/24 to any port 2222", a.ausgabe),
                        a.ausgabe)
