-- MySQL dump 10.13  Distrib 8.0.36, for Linux (x86_64)
--
-- Host: localhost    Database: epm_beispiel
-- ------------------------------------------------------
-- Erfundene Beispieldaten für die Tests des EPM-Imports. Kein Bezug zu echten Personen.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET TIME_ZONE='+00:00' */;


DROP TABLE IF EXISTS `benutzerdaten`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
CREATE TABLE `benutzerdaten` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `Benutzername` varchar(50) COLLATE utf8mb3_german2_ci NOT NULL,
  `Kennwort` varchar(32) COLLATE utf8mb3_german2_ci NOT NULL,
  `Rechte` int NOT NULL DEFAULT '100',
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `benutzerdaten` WRITE;
/*!40000 ALTER TABLE `benutzerdaten` DISABLE KEYS */;
INSERT INTO `benutzerdaten` VALUES (1,'e.beispiel','8402c9af51cd47de57ace27a06061488',10000),(2,'a.muster','ccb1ef2f3b00d0299144ee0ecca3af01',1000),(3,'verwaltung','9d21e1ea8d64b2a31acb211c8c4cc1ab',100000),(4,'b.betrachter','f6646d1fa164462b7c5c2a137b4ba5d4',100);
/*!40000 ALTER TABLE `benutzerdaten` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `versorger`;
CREATE TABLE `versorger` (
  `VersorgerID` int NOT NULL AUTO_INCREMENT,
  `firma` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `name` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `tel` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  PRIMARY KEY (`VersorgerID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `versorger` WRITE;
/*!40000 ALTER TABLE `versorger` DISABLE KEYS */;
INSERT INTO `versorger` VALUES (0,'-','-','',''),(1,'Homecare Nord (erfunden)','Frau Probe','probe@example.org','0000 111111'),(2,'Homecare Nord (erfunden)','Herr Muster','muster@example.org','0000 222222'),(3,'Apotheke Süd (erfunden)','','keine-adresse','0000 333333');
/*!40000 ALTER TABLE `versorger` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `patienten`;
CREATE TABLE `patienten` (
  `PatientenID` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_german2_ci NOT NULL,
  `vorname` varchar(255) COLLATE utf8mb3_german2_ci NOT NULL,
  `geschlecht` varchar(1) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `geburtsdatum` date DEFAULT NULL,
  `adresse` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `plz` int DEFAULT NULL,
  `stadt` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `telefonnummer` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `barzt` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `versorger` int DEFAULT NULL,
  `diagnose` text COLLATE utf8mb3_german2_ci,
  `therapie` text COLLATE utf8mb3_german2_ci,
  `kontaktaufnahme` text COLLATE utf8mb3_german2_ci,
  `empfehlung` text COLLATE utf8mb3_german2_ci,
  `dokumente` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `gewicht` decimal(6,1) DEFAULT NULL,
  `groesse` decimal(6,2) DEFAULT NULL,
  `katheter` varchar(32) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `NickAll` varchar(11) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `edit` varchar(150) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `lastchange` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`PatientenID`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `patienten` WRITE;
/*!40000 ALTER TABLE `patienten` DISABLE KEYS */;
INSERT INTO `patienten` VALUES (1,'Musterfrau','Erika','w','1961-03-14','Teststraße 1',48341,'Altenberge','erika@example.org','0000 000001','Dr. Hausmann (erfunden)',1,'Kurzdarmsyndrom nach Resektion (erfunden).\n\nRestdarm ca. 80 cm.\nColon in Kontinuität.','<p><b>Aktuell:</b> parenterale Ernährung 7x/Woche</p><div>Verlauf:</div><ul><li>02.01.2021 Beginn</li></ul><script>alert(1)</script>','Hausarzt','Gewichtskontrolle alle 4 Wochen','PatData/1/',64.5,166.0,'Portkatheter','Nein','e.beispiel','2023-05-02 10:11:12',NULL),(2,'MÃ¼ller','Max','m','1954-11-02','BeispielstraÃŸe 5',4109,'Leipzig','','0000 000002','',9,'Chronisches Darmversagen (erfunden) & <Verdacht>','','Überwiesen durch die Klinik am Beispielberg (erfunden), Station 4, nach längerem Aufenthalt; Überwiesen durch die Klinik am Beispielberg (erfunden), Station 4, nach längerem Aufenthalt; Überwiesen durch die Klinik am Beispielberg (erfunden), Station 4, nach längerem Aufenthalt;','','PatData/2/',78.0,1.81,'Broviac 2-lumig',NULL,'hans.alt','2022-11-30 16:45:00',NULL),(3,'Beispiel','Paula','w','0000-00-00','',0,'','','','',2,'','','','','',NULL,0.0,'ZVK','unbekannt','a.muster','2021-07-01 08:00:00',NULL),(4,'Probe','Jonas','m','1975-01-30','',44135,'Dortmund','','','',3,'Diagnose (erfunden)','','','','',70.0,176.0,'Power PICC','unbekannt','a.muster','2019-12-01 09:30:00','2020-01-15 08:00:00'),(5,'Test','Hanna','w','1949-09-09','Musterweg 2',48143,'Münster','hanna(at)example','0000 000005','',0,'','','','','',58.0,16.0,'Nein','Ja','E.Beispiel','2023-06-10 12:00:00',NULL),(6,'Demo','Karl','m','1958-05-17','',48143,'Münster','','','',1,'','','','','',NULL,172.0,'','vielleicht','a.muster','2018-03-03 10:00:00','2018-04-01 00:00:00'),(7,'Vorlage','Vera','w','1970-02-02','',48143,'Münster','','','',3,'','','','','',NULL,170.0,'Portkatheter','Nein','a.muster','2024-01-05 10:00:00',NULL);
/*!40000 ALTER TABLE `patienten` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `gewichte`;
CREATE TABLE `gewichte` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `PatID` int NOT NULL,
  `gewicht` decimal(6,2) NOT NULL,
  `lastchange` datetime DEFAULT NULL,
  `edit` varchar(150) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `gewichte` WRITE;
/*!40000 ALTER TABLE `gewichte` DISABLE KEYS */;
INSERT INTO `gewichte` VALUES (1,1,64.5,'2023-01-10 09:00:00','e.beispiel'),(2,1,0.0,'2023-02-10 09:00:00','e.beispiel'),(3,1,9999.0,'2023-03-10 09:00:00','a.muster'),(4,2,78.25,'2022-10-01 14:30:00','hans.alt'),(5,77,60.0,'2022-10-02 14:30:00','a.muster'),(6,4,70.0,'2019-11-11 11:11:11','a.muster'),(7,1,640.0,'2023-04-10 09:00:00','e.beispiel'),(8,2,77.0,NULL,'hans.alt'),(9,1,63.8,'2023-05-10 09:00:00',''),(10,7,61.0,'2024-01-05 10:05:00','a.muster');
/*!40000 ALTER TABLE `gewichte` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `kontakte`;
CREATE TABLE `kontakte` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `PatID` int NOT NULL,
  `kontakt` text COLLATE utf8mb3_german2_ci,
  `lastchange` datetime DEFAULT NULL,
  `edit` varchar(150) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `kontakte` WRITE;
/*!40000 ALTER TABLE `kontakte` DISABLE KEYS */;
INSERT INTO `kontakte` VALUES (1,1,'Telefonat: Befinden stabil, Infusion läuft ohne Probleme.\nRückruf in 4 Wochen.','2023-01-10 09:05:00','e.beispiel'),(2,1,'<p>Versorger meldet <b>Lieferung</b> bestätigt</p>','2023-02-01 15:00:00','a.muster'),(3,2,'RÃ¼ckfrage zur Laufzeit, Mutter sagt: \'alles gut\' \\ Ende','2022-10-05 10:00:00','hans.alt'),(4,99,'Kontakt ohne Patient','2022-10-05 10:00:00','a.muster'),(5,2,'','2022-10-06 10:00:00','a.muster'),(6,4,'Kontakt eines gelöschten Patienten','2019-11-12 10:00:00','a.muster');
/*!40000 ALTER TABLE `kontakte` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `infusionen`;
CREATE TABLE `infusionen` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `PatID` int NOT NULL,
  `created` datetime DEFAULT NULL,
  `created_by` varchar(150) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `lastchange` datetime DEFAULT NULL,
  `edit` varchar(150) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `kcal` varchar(20) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `ml` decimal(8,2) DEFAULT NULL,
  `volml` decimal(8,2) DEFAULT NULL,
  `voll` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `glucose` decimal(8,2) DEFAULT NULL,
  `glucosel` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `amino` decimal(8,2) DEFAULT NULL,
  `aminol` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `dipeptamin` decimal(8,2) DEFAULT NULL,
  `human` decimal(8,2) DEFAULT NULL,
  `humanl` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `lipide` decimal(8,2) DEFAULT NULL,
  `lipidel` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `omegaven` decimal(8,2) DEFAULT NULL,
  `natrium` decimal(8,2) DEFAULT NULL,
  `kalium` decimal(8,2) DEFAULT NULL,
  `phosphat` decimal(8,2) DEFAULT NULL,
  `calcium` decimal(8,2) DEFAULT NULL,
  `magnesium` decimal(8,2) DEFAULT NULL,
  `spurenelemente` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `vitamine` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `medi` varchar(255) COLLATE utf8mb3_german2_ci DEFAULT NULL,
  `lzh` decimal(5,1) DEFAULT NULL,
  `lzml` decimal(8,2) DEFAULT NULL,
  `kommentar` text COLLATE utf8mb3_german2_ci,
  `pantozol` int DEFAULT '0',
  `panzeit` int DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_german2_ci;

LOCK TABLES `infusionen` WRITE;
/*!40000 ALTER TABLE `infusionen` DISABLE KEYS */;
INSERT INTO `infusionen` VALUES (1,1,'2021-01-02 10:00:00','e.beispiel','2021-01-02 10:30:00','e.beispiel','1115',2257.5,500.0,'Sterofundin',150.0,'-',60.0,'Glamin 13,4%',0.0,0.0,'-',30.0,'Clinoleic 20 %',0.0,78.0,40.0,18.0,7.0,10.0,'Addel N','Soluvit N | Vitalipid adult','Taurolin 2%',12.0,0.0,'Testplan – keine echte Verordnung',1,5),(2,1,'2022-06-01 09:00:00','e.beispiel','2022-06-02 08:00:00','a.muster','433.564',2257.5,500.0,'NaCl 0.9 %',175.0,'',70.0,'Glamin',0.0,20.0,'Humanalbumin 20%',40.0,'Clinoleik 20%',0.0,80.0,40.0,18.0,7.0,10.0,'Addel N','Cernevit','Taurolin 2% | Heparin 100 I.E. nach Bedarf',14.0,180.0,'',0,5),(3,2,'2022-09-15 12:00:00','hans.alt',NULL,'hans.alt','1500',2700.0,0.0,'-',9000.0,'Glucose 70 %',72.0,'Aminoplasmal 10 %',0.0,0.0,'',36.0,'SMOF-Lipid',0.0,0.0,0.0,0.0,0.0,0.0,'-','-','-',0.0,0.0,'<p>Kommentar mit <i>HTML</i></p>',7,NULL),(4,4,'2019-10-01 08:00:00','a.muster','2019-10-01 08:00:00','a.muster','900',2450.0,0.0,'-',100.0,'',50.0,'Glamin 13,4%',0.0,0.0,'',20.0,'Clinoleic 20 %',0.0,0.0,0.0,0.0,0.0,0.0,'-','-','-',10.0,0.0,'',0,NULL),(5,55,'2019-10-01 08:00:00','a.muster','2019-10-01 08:00:00','a.muster','900',2450.0,0.0,'-',100.0,'',50.0,'',0.0,0.0,'',20.0,'',0.0,0.0,0.0,0.0,0.0,0.0,'-','-','-',10.0,0.0,'',0,NULL),(6,7,'2024-01-05 10:10:00','a.muster','2024-01-05 10:10:00','a.muster','940',2135.0,500.0,'Sterofundin',100.0,'',60.0,'Glamin 13,4%',0.0,0.0,'',30.0,'Clinoleic 20 %',0.0,60.0,40.0,10.0,5.0,5.0,'Addel N','Cernevit','Taurolin 2%',12.0,0.0,'',1,5);
/*!40000 ALTER TABLE `infusionen` ENABLE KEYS */;
UNLOCK TABLES;

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

-- Dump completed on 2026-10-02  9:00:00
