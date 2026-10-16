from harmonize.cache import content_key, file_digest


def _write(p, text):
    p.write_text(text)
    return str(p)


def test_content_key_is_deterministic(tmp_path):
    a = _write(tmp_path / "a.csv", "x\n1\n")
    k1 = content_key([a], "0.1.0", '{"spec":1}')
    k2 = content_key([a], "0.1.0", '{"spec":1}')
    assert k1 == k2


def test_content_key_changes_with_input(tmp_path):
    a = _write(tmp_path / "a.csv", "x\n1\n")
    k1 = content_key([a], "0.1.0", '{"spec":1}')
    _write(tmp_path / "a.csv", "x\n2\n")
    k2 = content_key([a], "0.1.0", '{"spec":1}')
    assert k1 != k2


def test_content_key_changes_with_spec_and_version(tmp_path):
    a = _write(tmp_path / "a.csv", "x\n1\n")
    base = content_key([a], "0.1.0", '{"spec":1}')
    assert base != content_key([a], "0.1.0", '{"spec":2}')
    assert base != content_key([a], "0.2.0", '{"spec":1}')


def test_source_order_does_not_matter(tmp_path):
    a = _write(tmp_path / "a.csv", "x\n1\n")
    b = _write(tmp_path / "b.csv", "x\n2\n")
    assert content_key([a, b], "0.1.0", "{}") == content_key([b, a], "0.1.0", "{}")


def test_file_digest_stable(tmp_path):
    a = _write(tmp_path / "a.csv", "hello\n")
    assert file_digest(a) == file_digest(a)
