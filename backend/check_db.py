#!/usr/bin/env python
"""Quick script to check database contents"""
from app.database import SessionLocal
from app.models.matching import MatchCandidate, ReconciliationProcess

db = SessionLocal()

print("=== RECONCILIATION PROCESSES ===")
processes = db.query(ReconciliationProcess).all()
for p in processes:
    print(f"ID: {p.id} - {p.process_name}")

print("\n=== MATCH CANDIDATES (last 20) ===")
candidates = db.query(MatchCandidate).order_by(MatchCandidate.id.desc()).limit(20).all()
for c in candidates:
    status = ["PENDING", "VALID", "TOLAK"][max(0, min(2, c.is_accepted + 1))]
    print(f"{c.id:3d} | {c.candidate_idpel:20s} | accepted: {c.is_accepted} ({status})")

db.close()
