#!/usr/bin/env python3
"""Synchronization of explicit Grist fields, without deletion or silent deduplication."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


def api(base, token, method, doc, table, body=None):
    path = "/api/docs/{}/tables/{}/records".format(
        urllib.parse.quote(doc, safe=""), urllib.parse.quote(table, safe=""))
    url = base.rstrip("/") + path
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            detail = exc.read(500).decode("utf-8", "replace")
            raise RuntimeError(f"Échec API HTTP {exc.code}, document {doc}, table {table}: {detail[:300]}") from None
        except urllib.error.URLError as exc:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Connexion impossible à Grist : {exc.reason}") from None


def make_index(records, keys, label):
    index = {}
    for record in records:
        fields = record["fields"]
        missing = [k for k in keys if k not in fields or fields[k] is None or fields[k] == ""]
        if missing:
            raise ValueError(f"{label} : clé incomplète ({missing}), ligne {record.get('id')}")
        key = tuple(json.dumps(fields[k], sort_keys=True, ensure_ascii=False) for k in keys)
        if key in index:
            raise ValueError(f"{label} : doublon sur la clé {keys} (lignes {index[key].get('id')} et {record.get('id')}). Arrêt sans écriture.")
        index[key] = record
    return index


def prepare(source, target, keys, columns):
    source_idx = make_index(source, keys, "Source")
    target_idx = make_index(target, keys, "Destination")
    creates, updates = [], []
    for key, src in source_idx.items():
        missing = [c for c in columns if c not in src["fields"]]
        if missing:
            raise ValueError(f"Colonne(s) source absente(s) : {missing}; vérifie les identifiants de colonnes dans config.json")
        fields = {c: src["fields"][c] for c in columns}
        old = target_idx.get(key)
        if old is None:
            creates.append({"fields": fields})
        else:
            changes = {c: v for c, v in fields.items() if c not in keys and old["fields"].get(c) != v}
            if changes:
                updates.append({"id": old["id"], "fields": changes})
    return creates, updates


def chunks(items, n):
    for i in range(0, len(items), n):
        yield items[i:i+n]


def main():
    parser = argparse.ArgumentParser(description="Copie maîtrisée d'une table Grist vers plusieurs documents")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--apply", action="store_true", help="Écrit dans les documents de destination (sinon simulation)")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    token = os.environ.get("GRIST_API_KEY", "").strip()
    if not token:
        raise ValueError("Secret GRIST_API_KEY manquant")
    keys = cfg["key_columns"]
    columns = cfg["sync_columns"]
    if not keys or not columns or any(k not in columns for k in keys) or len(set(columns)) != len(columns):
        raise ValueError("key_columns et sync_columns doivent être non vides, uniques et cohérentes")
    if len(set(keys)) != len(keys):
        raise ValueError("Clés répétées")
    source = cfg["source"]
    destinations = [d for d in cfg["destinations"] if d.get("enabled")]
    if not destinations:
        raise ValueError("Aucune destination activée (enabled: true)")
    ids = [(d["document_id"], d["table_id"]) for d in destinations]
    if len(ids) != len(set(ids)) or (source["document_id"], source["table_id"]) in ids:
        raise ValueError("Destination en double ou identique à la source")
    base = cfg["base_url"]
    if not base.startswith("https://"):
        raise ValueError("L'API Grist doit être appelée en HTTPS")
    source_records = api(base, token, "GET", source["document_id"], source["table_id"])["records"]
    make_index(source_records, keys, "Source")
    if not source_records:
        raise ValueError("Source vide : arrêt prudent")
    print(f"Source : {len(source_records)} enregistrements. Mode : {'ÉCRITURE' if args.apply else 'SIMULATION'}")
    # Prépare TOUS les plans avant la moindre écriture, pour limiter les erreurs partielles.
    plans = []
    for d in destinations:
        target = api(base, token, "GET", d["document_id"], d["table_id"])["records"]
        new, changed = prepare(source_records, target, keys, columns)
        total = len(new) + len(changed)
        if total > cfg.get("max_changes_per_destination", 20000):
            raise ValueError(f"{d['name']} : {total} changements dépassent le seuil de sécurité")
        print(f"{d['name']} : {len(new)} ajouts ; {len(changed)} mises à jour ; {len(target)} lignes existantes ; 0 suppression")
        plans.append((d, new, changed))
    if not args.apply:
        print("Simulation terminée. Aucun document modifié.")
        return
    batch = int(cfg.get("batch_size", 100))
    if not 1 <= batch <= 500:
        raise ValueError("batch_size doit être compris entre 1 et 500")
    for d, new, changed in plans:
        # Updates first, then additions. One destination may be partially updated on an API error.
        for group in chunks(changed, batch):
            api(base, token, "PATCH", d["document_id"], d["table_id"], {"records": group})
        for group in chunks(new, batch):
            api(base, token, "POST", d["document_id"], d["table_id"], {"records": group})
        print(f"OK {d['name']} : synchronisation terminée")
    print("Synchronisation achevée.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        sys.exit(1)
