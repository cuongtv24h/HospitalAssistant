from unittest.mock import Mock

from apps.api.foundation.knowledge.repository.lexical_search import (
    build_sparse_tsquery,
    lexical_search,
)


def test_sparse_query_removes_stop_words_and_uses_or_terms():
    query = build_sparse_tsquery("Quy trình khám bệnh bằng bảo hiểm y tế")

    assert "bằng" not in query
    assert query == "quy | trình | khám | bệnh | bảo | hiểm | y | tế | bhyt"


def test_sparse_query_expands_bhyt_abbreviation():
    query = build_sparse_tsquery("Thủ tục khám BHYT")

    assert query == "thủ | tục | khám | bhyt | bảo | hiểm | y | tế"


def test_lexical_search_passes_sparse_query_to_postgres():
    cursor = Mock()
    cursor.fetchall.return_value = []

    assert lexical_search(cursor, "khám bệnh bằng bảo hiểm y tế") == []

    parameters = cursor.execute.call_args.args[1]
    assert parameters[0] == "khám | bệnh | bảo | hiểm | y | tế | bhyt"
    assert parameters[1] == parameters[0]
    assert parameters[2] == 5
