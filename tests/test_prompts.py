from agent_primer.prompts import new_project_planner_prompt


def test_new_project_planner_prompt_requests_verification_ready_context():
    prompt = new_project_planner_prompt("new-app", "A focused developer tool")

    assert "provisional" in prompt
    assert "verification_commands" in prompt
    assert "5 proposals" in prompt
    assert "do not invent certainty" in prompt
