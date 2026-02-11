from src.agent_mode import AgentMode


def _make_agent():
    agent = AgentMode.__new__(AgentMode)
    agent._get_assistant_settings = lambda: ("아이", "cheerful")
    return agent


def test_sanitize_response_removes_intro_and_emoji():
    agent = _make_agent()
    response = "안녕하세요! 저는 아이입니다! 반가워요 😊"
    assert agent._sanitize_response(response) == "반가워요"


def test_split_text_for_tts_long_text_to_two_or_three_chunks():
    agent = _make_agent()
    response = (
        "오늘 일정을 확인해 보니 오후 세 시 회의가 있고, "
        "저녁 여섯 시에는 운동 약속이 있어요. 준비할 게 있으면 미리 알려드릴게요."
    )
    chunks = agent.split_text_for_tts(response, max_chunks=3)
    assert 2 <= len(chunks) <= 3
    assert "".join(chunks).replace(" ", "") == response.replace(" ", "")


def test_prepare_tts_chunks_sanitizes_text():
    agent = _make_agent()
    response = "저는 아이입니다! 오늘은 날씨가 좋아요 😊 산책 어떠세요?"
    chunks = agent.prepare_tts_chunks(response, max_chunks=3)
    assert chunks
    assert all("아이입니다" not in chunk for chunk in chunks)
    assert all("😊" not in chunk for chunk in chunks)
