"""Losslessly re-encode ledger Parquet storage; never run or alter research analysis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

LEDGER_DIR = "03_FINAL_RESULTS/transaction_costs/trade_ledger"
CHECKS = "07_VALIDATION_AND_TESTS/validation_results/lossless_recompression_checks.csv"
REPORT = "09_REPORTS/lossless_compression_report.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def encode_one(source, destination, level):
    original_hash = sha(source)
    table = pq.read_table(source)
    floating = [f.name for f in table.schema if pa.types.is_floating(f.type)]
    dictionary = [
        f.name for f in table.schema
        if f.name not in floating or pc.count_distinct(table[f.name]).as_py() <= 128
    ]
    byte_split = [n for n in floating if n not in dictionary]
    pq.write_table(
        table, destination, compression="zstd", compression_level=level,
        use_dictionary=dictionary, use_byte_stream_split=byte_split,
        data_page_version="2.0",
    )
    decoded = pq.read_table(destination)
    assert table.num_rows == decoded.num_rows
    assert table.schema.equals(decoded.schema, check_metadata=True)
    compared_float_values = 0
    for i in range(table.num_columns):
        a = table.column(i).combine_chunks()
        b = decoded.column(i).combine_chunks()
        assert a.is_valid().equals(b.is_valid()), table.schema.names[i]
        if pa.types.is_floating(a.type):
            valid = a.is_valid().to_numpy(zero_copy_only=False)
            original = a.to_numpy(zero_copy_only=False)[valid]
            compressed = b.to_numpy(zero_copy_only=False)[valid]
            # Byte equality preserves float64 precision, signed zeros and NaN
            # payloads of valid values. Invalid slots are checked by null mask.
            assert original.dtype == compressed.dtype
            assert original.tobytes() == compressed.tobytes(), table.schema.names[i]
            compared_float_values += len(original)
        else:
            assert a.equals(b), table.schema.names[i]
    assert sha(source) == original_hash
    record = dict(
        relative_path=LEDGER_DIR + "/" + source.name,
        source_sha256=original_hash, delivery_sha256=sha(destination),
        source_size_bytes=source.stat().st_size,
        delivery_size_bytes=destination.stat().st_size,
        rows=table.num_rows, columns=table.num_columns,
        floating_values_compared_bit_for_bit=compared_float_values,
        schema_and_metadata_equal=True, null_masks_equal=True,
        floating_bits_equal=True, nonfloating_values_equal=True,
        row_order_preserved=True, status="PASS",
        compression="zstd", compression_level=level,
        data_page_version="2.0", dictionary_columns=json.dumps(dictionary),
        byte_stream_split_columns=json.dumps(byte_split),
    )
    print(source.name, record["source_size_bytes"], "->", record["delivery_size_bytes"], "PASS", flush=True)
    return record


def update_manifest(package):
    path = package / "00_README/FILE_MANIFEST.csv"
    entries = {r["relative_path"]: r for r in read_csv(path)}
    descriptions = {
        "01_FINAL_CODE/repack_lossless.py": "无损账本存储重编码及逐列位级校验脚本；不运行分析",
        CHECKS: "27个账本的原/新hash、大小及数值/类型/空值逐项一致性证据",
        REPORT: "无损压缩配置、变更范围、保留文件与完整性记录",
    }
    for file in sorted(f for f in package.rglob("*") if f.is_file()):
        rel = file.relative_to(package).as_posix()
        if rel == "00_README/FILE_MANIFEST.csv":
            continue
        if rel not in entries:
            entries[rel] = dict(
                category=rel.split("/")[0], filename=file.name,
                relative_path=rel, description=descriptions[rel],
                generated_by="repack_lossless.py", final_or_reference="final",
                notes="Storage-only operation; empirical values unchanged.",
                source_path="", sha256="", size_bytes="",
            )
        row = entries[rel]
        row["sha256"] = sha(file)
        row["size_bytes"] = file.stat().st_size
        if rel.startswith(LEDGER_DIR + "/"):
            row["generated_by"] = "repair.backtests.run_all; lossless storage re-encoding by repack_lossless.py"
            row["notes"] += " Parquet byte hash changed only through lossless Zstd19/byte-stream-split encoding; all decoded values/types/nulls/metadata checked in lossless_recompression_checks.csv."
    write_csv(path, sorted(entries.values(), key=lambda r: r["relative_path"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--level", type=int, default=19)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    assert not destination.exists(), "Use a new destination. Source and previous deliveries are never overwritten."
    assert source != destination and source not in destination.parents
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    ledger_source = source / LEDGER_DIR
    def ignore(folder, names):
        return [n for n in names if n.endswith(".parquet")] if Path(folder) == ledger_source else []
    shutil.copytree(source, destination, ignore=ignore)
    ledgers = sorted(ledger_source.glob("*.parquet"))
    assert len(ledgers) == 27
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda f: encode_one(f, destination / LEDGER_DIR / f.name, args.level), ledgers))
    assert sum(r["rows"] for r in rows) == 6448275
    write_csv(destination / CHECKS, rows)
    shutil.copy2(Path(__file__), destination / "01_FINAL_CODE/repack_lossless.py")
    note = """

## 无损压缩版（512 MB上传限制）

为满足上传大小限制，仅对27个交易账本Parquet重新编码：Zstd level19，连续浮点列使用byte-stream-split，低基数列保留dictionary，data_page_version=2.0。全部6,448,275行的浮点有效值逐位比较，其他值、行顺序、类型、空值位置及schema metadata全部一致；未降为float32、未舍入、未删行/列/文件，未重新运行回测或统计分析。原CSV、LaTeX表、图件、数据输入和分析代码保持字节不变。

文件字节hash随存储编码改变，FILE_MANIFEST已更新；原/新账本hash与位级核验在07_VALIDATION_AND_TESTS/validation_results/lossless_recompression_checks.csv。copy_integrity_checks.csv保留prior_delivery_sha256并以verification_basis区分原样复制与无损重编码。原始研究日志和32项测试记录保留，本次新增的是存储一致性核验，不冒充新跑分析。原始大ZIP及原交付目录未覆盖。压缩复现脚本为01_FINAL_CODE/repack_lossless.py，仍使用原环境的PyArrow23.0.1；外层为普通DEFLATE ZIP。
"""
    for rel in ["00_README/README_MASTER.md", "00_README/CHANGELOG.md", "07_VALIDATION_AND_TESTS/test_summary.md"]:
        path = destination / rel
        path.write_text(path.read_text() + note)
    recoded = {r["relative_path"]: r for r in rows}
    proof_path = destination / "07_VALIDATION_AND_TESTS/validation_results/copy_integrity_checks.csv"
    proof = read_csv(proof_path)
    for r in proof:
        r["prior_delivery_sha256"] = r["delivery_sha256"]
        if r["relative_path"] in recoded:
            row = recoded[r["relative_path"]]
            assert r["delivery_sha256"] == row["source_sha256"]
            r["delivery_sha256"] = row["delivery_sha256"]
            r["verification_basis"] = "all_decoded_values_types_nulls_metadata_identical; storage_encoding_changed"
        else:
            r["verification_basis"] = "byte_identical_copy"
    write_csv(proof_path, proof)
    allowed = set(recoded) | {
        "00_README/README_MASTER.md", "00_README/CHANGELOG.md", "00_README/FILE_MANIFEST.csv",
        "07_VALIDATION_AND_TESTS/test_summary.md",
        "07_VALIDATION_AND_TESTS/validation_results/copy_integrity_checks.csv",
        "07_VALIDATION_AND_TESTS/validation_results/packaging_validation.json",
    }
    unchanged = 0
    for f in source.rglob("*"):
        if f.is_file():
            rel = f.relative_to(source).as_posix()
            assert (destination / rel).exists()
            if rel not in allowed:
                assert sha(f) == sha(destination / rel), rel
                unchanged += 1
    report = dict(
        started_at_utc=start, finished_reencoding_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_directory=str(source), original_source_modified=False,
        original_files_removed=0, analysis_rerun=False, dataframe_values_changed=False,
        unchanged_original_files_verified_byte_for_byte=unchanged,
        pyarrow_version=pa.__version__, parquet_compression="zstd", level=args.level,
        float_encoding="BYTE_STREAM_SPLIT for >128 distinct floating values; dictionary otherwise",
        data_page_version="2.0", ledger_files=len(rows), ledger_rows=sum(r["rows"] for r in rows),
        original_ledger_bytes=sum(r["source_size_bytes"] for r in rows),
        recompressed_ledger_bytes=sum(r["delivery_size_bytes"] for r in rows),
        floating_values_compared_bit_for_bit=sum(r["floating_values_compared_bit_for_bit"] for r in rows),
        checks_status="PASS", limit_bytes=512000000,
        archive_validation="Run after this report is included; final CRC/size/hash proof is next to the ZIP.",
    )
    (destination / REPORT).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    update_manifest(destination)
    sys.path.insert(0, str(destination / "01_FINAL_CODE"))
    import check_delivery
    # Reuse the existing portable delivery audit, without invoking any research.
    audit = check_delivery.check(destination)
    audit_path = destination / "07_VALIDATION_AND_TESTS/validation_results/packaging_validation.json"
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    check_delivery.refresh_manifest(destination, audit_path)
    check_delivery.check(destination)
    result = check_delivery.zip_audit(destination, args.zip.resolve())
    result["size_limit_bytes"] = 512000000
    result["under_512_decimal_MB"] = result["size_bytes"] <= 512000000
    args.zip.with_suffix(".verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    assert result["under_512_decimal_MB"], "Archive not yet under the conservative decimal-MB limit."


if __name__ == "__main__":
    main()
