import base64

from httpie_rich_terminal.protocols.kitty import KITTY_CHUNK_SIZE, KittyProtocol

PROTO = KittyProtocol()


def test_only_accepts_png():
    assert PROTO.accepts_format("PNG") is True
    assert PROTO.accepts_format("JPEG") is False
    assert PROTO.accepts_format("GIF") is False


def test_accepts_format_is_case_insensitive():
    assert PROTO.accepts_format("png") is True


def test_single_chunk_payload_is_one_escape_sequence():
    data = b"tiny"
    encoded = base64.standard_b64encode(data).decode("ascii")

    out = PROTO.render(data, "PNG")

    assert out == f"\x1b_Ga=T,f=100,q=2,m=0;{encoded}\x1b\\\n"


def test_multi_chunk_splits_on_the_4096_boundary():
    # Choose a size whose base64 form is exactly 2 chunks + a remainder.
    data = b"\xff" * 6000
    encoded = base64.standard_b64encode(data).decode("ascii")
    assert len(encoded) > KITTY_CHUNK_SIZE

    out = PROTO.render(data, "PNG")
    sequences = [s for s in out.rstrip("\n").split("\x1b\\") if s]

    # First sequence carries the full control data and m=1.
    assert sequences[0].startswith(f"\x1b_Ga=T,f=100,q=2,m=1;{encoded[:KITTY_CHUNK_SIZE]}")
    # Continuation sequences carry only m.
    assert sequences[1].startswith("\x1b_Gm=")
    assert "a=T" not in sequences[1]
    # The final sequence closes the transfer.
    assert sequences[-1].startswith("\x1b_Gm=0;")


def test_all_chunks_except_the_last_are_multiples_of_four():
    data = b"\xab" * 9000
    out = PROTO.render(data, "PNG")

    payloads = []
    for seq in out.rstrip("\n").split("\x1b\\"):
        if not seq:
            continue
        payloads.append(seq.split(";", 1)[1])

    for payload in payloads[:-1]:
        assert len(payload) % 4 == 0


def test_payload_reassembles_to_the_original_bytes():
    data = bytes(range(256)) * 40
    out = PROTO.render(data, "PNG")

    payloads = []
    for seq in out.rstrip("\n").split("\x1b\\"):
        if not seq:
            continue
        payloads.append(seq.split(";", 1)[1])

    assert base64.standard_b64decode("".join(payloads)) == data


def test_payload_of_exactly_one_chunk_boundary():
    # base64 of 3072 bytes is exactly 4096 chars -> one full chunk, then a
    # terminating empty chunk.
    data = b"\x01" * 3072
    encoded = base64.standard_b64encode(data).decode("ascii")
    assert len(encoded) == KITTY_CHUNK_SIZE

    out = PROTO.render(data, "PNG")
    sequences = [s for s in out.rstrip("\n").split("\x1b\\") if s]

    assert len(sequences) == 2
    assert sequences[0] == f"\x1b_Ga=T,f=100,q=2,m=1;{encoded}"
    assert sequences[1] == "\x1b_Gm=0;"


def test_output_ends_with_a_newline_so_the_prompt_is_not_glued_to_the_image():
    assert PROTO.render(b"x", "PNG").endswith("\n")


def test_middle_chunks_are_marked_as_continuations():
    # 9000 bytes -> 12000 base64 chars -> 3 chunks, so there is a genuine
    # middle. Emitting m=0 early would truncate the image on a real terminal
    # while every other assertion in this file still passed.
    data = b"\xcd" * 9000

    out = PROTO.render(data, "PNG")
    controls = [s.split(";", 1)[0] for s in out.rstrip("\n").split("\x1b\\") if s]

    assert len(controls) == 3
    assert controls[0].endswith("m=1")
    assert controls[1] == "\x1b_Gm=1"
    assert controls[2] == "\x1b_Gm=0"
