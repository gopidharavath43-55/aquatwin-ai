with open("api_server.py", "r", encoding="utf-8") as f:
    src = f.read()

old_block = """        x_df = pd.DataFrame([row[xgb_cols]])
    p_1m = float(np.clip(xgb_1m.predict(x_df)[0], 15.0, 98.5))
    p_6m = float(np.clip(xgb_6m.predict(x_df)[0], 15.0, 98.5))

    win = grp[dl_feats].tail(seq_len).values.astype(np.float32).copy()
    win[-1] = row[dl_feats].values.astype(np.float32)"""

new_block = """        safe_row = {c: float(pd.to_numeric(row[c], errors="coerce") if pd.notna(row[c]) else 0.0) for c in xgb_cols}
    safe_row["month"] = int(round(safe_row["month"]))
    safe_row["anomaly_flag"] = int(round(safe_row["anomaly_flag"]))
    x_df = pd.DataFrame([safe_row])[xgb_cols]
    p_1m = float(np.clip(xgb_1m.predict(x_df)[0], 15.0, 98.5))
    p_6m = float(np.clip(xgb_6m.predict(x_df)[0], 15.0, 98.5))

    win = grp[dl_feats].tail(seq_len).apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32).copy()
    if len(win) < seq_len:
        pad = np.repeat(win[:1], seq_len - len(win), axis=0)
        win = np.vstack([pad, win])
    win[-1] = np.array([float(pd.to_numeric(row[c], errors="coerce") if pd.notna(row[c]) else 0.0) for c in dl_feats], dtype=np.float32)"""

if old_block in src:
    src = src.replace(old_block, new_block, 1)
    with open("api_server.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("Patched /simulate numeric safety cleanly.")
else:
    print("Check api_server.py lines around x_df.")
