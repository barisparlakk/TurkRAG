import csv

from scripts.repair_generated_eval_csv import repair_generated_eval_csv


def test_repair_generated_eval_csv_restores_blank_rows_from_matching_source(tmp_path):
    target = tmp_path / "eval_set_generated.csv"
    source = tmp_path / "generated_questions.csv"
    target.write_text(
        "\n".join([
            "question,ground_truth,relevant_doc,doc_id,chunk_index,source_text,verified",
            ",,doc-a,id-a,0,chunk a,False",
            "Mevcut soru,Mevcut yanit,doc-b,id-b,1,chunk b,True",
        ]),
        encoding="utf-8",
    )
    source.write_text(
        "\n".join([
            "question,ground_truth,relevant_doc,doc_id,chunk_index,source_text,verified",
            "Yeni soru,Yeni yanit,doc-a,id-a,0,chunk a,False",
            "Farkli soru,Farkli yanit,doc-b,id-b,1,chunk b,True",
        ]),
        encoding="utf-8",
    )

    repaired_count = repair_generated_eval_csv(target, source)

    assert repaired_count == 1
    with target.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["question"] == "Yeni soru"
    assert rows[0]["ground_truth"] == "Yeni yanit"
    assert rows[1]["question"] == "Mevcut soru"
