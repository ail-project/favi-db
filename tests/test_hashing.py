from app.services.hashing import compute_hashes


def test_compute_hashes_does_not_return_content():
    hashes = compute_hashes(b"fake favicon bytes").as_dict()
    assert hashes["sha256"] == "15fe031d5b3e497528329e825d8790fd81d4dbcae3250acdaed0cd2c71ecf961"
    assert "mmh3" in hashes
    assert "fake favicon bytes" not in hashes.values()
