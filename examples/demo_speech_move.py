"""Example that runs STT -> LLM -> actuators."""
from voice import stt, tts
from brain import llm_gateway
from control import actuators


if __name__ == "__main__":
    command = stt.transcribe()
    action = llm_gateway.ask_llm(command, context={})
    if action["action"] == "move":
        actuators.move(action["params"]["dir"], action["params"]["duration"])
    audio = tts.synthesize("Action completed")
    print(f"Synthesized {len(audio)} bytes")
