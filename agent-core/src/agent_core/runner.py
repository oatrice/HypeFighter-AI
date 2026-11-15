"""Live match runner connecting Telemetry Receiver and Action Sender."""
import asyncio
import json
import os
import signal
import sys
from agent_core.models.telemetry import MatchSnapshot, EgoCentricIntent
from agent_core.receiver.udp_receiver import TelemetryUDPReceiver
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper
from agent_core.controller.action_sender import ActionUDPSender
from agent_core.controller.combo_engine import ComboEngine
from agent_core.tactician.tactical_brain import TacticalBrain


class MatchRunner:
    def __init__(
        self,
        telemetry_port: int = 9999,
        action_port: int = 9998,
        telemetry_file: str = "/tmp/framewhisper_telemetry.json",
        action_file: str = "/tmp/framewhisper_action.json",
    ):
        self.telemetry_port = telemetry_port
        self.action_port = action_port
        self.telemetry_file = telemetry_file
        self.action_file = action_file
        self.thought_file = "/tmp/framewhisper_thought.json"
        self.chat_file = "/tmp/framewhisper_chat.txt"
        self.gatekeeper = SafetyGatekeeper()
        self.combo_engine = ComboEngine()
        self.action_sender = ActionUDPSender(target_port=action_port)
        self.tactical_brain = TacticalBrain()
        self.receiver = TelemetryUDPReceiver(port=telemetry_port, on_snapshot=self.on_snapshot)
        self.running = False
        self._last_processed_frame = -1
        self._frame_count = 0
        self._latest_decision = None

    def on_snapshot(self, snapshot: MatchSnapshot):
        if snapshot.frame == self._last_processed_frame:
            return
        self._last_processed_frame = snapshot.frame
        self._frame_count += 1

        # Check for live spectator chat coaching from file (supports multiple queued messages)
        if os.path.exists(self.chat_file):
            try:
                with open(self.chat_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    os.remove(self.chat_file)
                    for line in content.splitlines():
                        line = line.strip()
                        if line:
                            self.tactical_brain.ingest_chat_message(line)
                            print(f"\n📩 [Live Chat Ingested]: \"{line}\"", flush=True)
            except Exception:
                pass

        self.tactical_brain.ingest_snapshot(snapshot)

        # Periodically consult tactical brain (every ~20 frames / 3Hz)
        desired_intent = None
        if self._frame_count % 20 == 0:
            summary = self.tactical_brain.summarize_window()
            decision = self.tactical_brain.fallback_tactical_rule(summary)
            desired_intent = decision.macro_intent
            self._latest_decision = decision

            # Write out thought state atomically for Floating Thought Bubble overlay
            try:
                tmp_thought = self.thought_file + ".tmp"
                with open(tmp_thought, "w", encoding="utf-8") as f:
                    f.write(decision.model_dump_json())
                os.replace(tmp_thought, self.thought_file)
            except Exception:
                pass

        # 60Hz deterministic safety gatekeeper evaluation
        action = self.gatekeeper.evaluate(snapshot, desired_intent=desired_intent)

        # Combo Engine & Hit-Confirm Chaining (Overrides standard intent if combo active, unless blocking/recovery required)
        if not action.is_reaction or action.reaction_type in ("PUNISH_IN_PLACE", "SUPER_PUNISH_IN_PLACE"):
            combo_action = self.combo_engine.update(snapshot)
            if combo_action is not None:
                action = combo_action
        else:
            if action.reaction_type and action.reaction_type.startswith("INSTANT_BLOCK"):
                self.combo_engine.reset()

        # Transmit concrete action back into Ikemen GO via UDP and atomic IPC fallback
        self.action_sender.send(action, frame=snapshot.frame)
        try:
            action_dict = self.action_sender.serialize_action(action, frame=snapshot.frame)
            tmp_act = self.action_file + ".tmp"
            with open(tmp_act, "w", encoding="utf-8") as f:
                f.write(json.dumps(action_dict))
            os.replace(tmp_act, self.action_file)
        except Exception:
            pass

        # Stream visual status to console
        cam_info = ""
        if "camera" in snapshot.meta or hasattr(snapshot, "camera"):
            cam = getattr(snapshot, "camera", None) or snapshot.meta.get("camera", {})
            if isinstance(cam, dict) and "zoom" in cam:
                cam_info = f" | Cam_Y:{cam.get('y', 0):.1f} Zoom:{cam.get('zoom', 1.0):.2f}x"

        if snapshot.frame % 30 == 0 or action.is_reaction or snapshot.p1.pos.y < -30 or snapshot.p2.pos.y < -30:
            p1_pos = f"({snapshot.p1.pos.x:.1f},{snapshot.p1.pos.y:.1f})"
            p2_pos = f"({snapshot.p2.pos.x:.1f},{snapshot.p2.pos.y:.1f})"
            cmd_info = f" CMD:{action.cmd}" if action.cmd else ""
            print(
                f"[F:{snapshot.frame:05d}] P1:{snapshot.p1.life:04d} {p1_pos} (P:{snapshot.p1.power}) | "
                f"P2:{snapshot.p2.life:04d} {p2_pos} | "
                f"Dist:{snapshot.distance:.1f} | "
                f"Action:{action.reaction_type or action.macro_intent.value} [{action.button.value}]{cmd_info}"
                f"{cam_info}",
                flush=True,
            )
            if action.cmd:
                print(f"  💥 [COMBO/SUPER EXECUTION]: {action.cmd} (Reaction: {action.reaction_type})", flush=True)
            # Display dual-channel thought stream every 60 frames (1 second) or when reaction occurs
            if self._latest_decision and (snapshot.frame % 60 == 0 or action.is_reaction):
                dec = self._latest_decision
                print(f"  🧠 [P1 Private Mind]: \"{dec.internal_monologue}\"", flush=True)
                print(f"  💬 [P1 In-Game Chat]: \"{dec.public_chat}\"", flush=True)
                if dec.audience_reply:
                    print(f"  📣 [P1 Crowd Reply]: \"{dec.audience_reply}\"", flush=True)

    async def _poll_file_fallback(self):
        """Polls IPC telemetry file if UDP packets are not arriving."""
        while self.running:
            if os.path.exists(self.telemetry_file):
                try:
                    with open(self.telemetry_file, "r") as f:
                        raw = f.read().strip()
                    if raw and raw.startswith("{") and raw.endswith("}"):
                        data = json.loads(raw)
                        # Remove or convert camera to meta
                        if "camera" in data:
                            data["meta"] = {"camera": data["camera"]}
                        snap = MatchSnapshot.model_validate(data)
                        self.on_snapshot(snap)
                except Exception:
                    pass
            await asyncio.sleep(0.005)  # Fast 200Hz poll to prevent frame skipping

    async def start(self):
        self.running = True
        await self.receiver.start()
        print(f"=== FrameWhisper AI Agent Core Running ===", flush=True)
        print(f"Telemetry Listening: UDP {self.telemetry_port} & IPC {self.telemetry_file}", flush=True)
        print(f"Action Injecting:   UDP {self.action_port} & IPC {self.action_file}", flush=True)
        asyncio.create_task(self._poll_file_fallback())
        while self.running:
            await asyncio.sleep(0.5)

    async def stop(self):
        self.running = False
        await self.receiver.stop()
        self.action_sender.close()
        print("FrameWhisper AI Agent Core Stopped.", flush=True)


async def main():
    runner = MatchRunner()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(runner.stop()))
        except NotImplementedError:
            pass

    try:
        await runner.start()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
