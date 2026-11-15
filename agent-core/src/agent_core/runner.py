"""Live match runner connecting 60Hz Telemetry Receiver and Action Sender."""
import asyncio
import signal
import sys
from agent_core.models.telemetry import MatchSnapshot, EgoCentricIntent
from agent_core.receiver.udp_receiver import TelemetryUDPReceiver
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper
from agent_core.controller.action_sender import ActionUDPSender
from agent_core.tactician.tactical_brain import TacticalBrain


class MatchRunner:
    def __init__(self, telemetry_port: int = 9999, action_port: int = 9998):
        self.telemetry_port = telemetry_port
        self.action_port = action_port
        self.gatekeeper = SafetyGatekeeper()
        self.action_sender = ActionUDPSender(target_port=action_port)
        self.tactical_brain = TacticalBrain()
        self.receiver = TelemetryUDPReceiver(port=telemetry_port, on_snapshot=self.on_snapshot)
        self.running = False
        self._frame_count = 0

    def on_snapshot(self, snapshot: MatchSnapshot):
        self._frame_count += 1
        self.tactical_brain.ingest_snapshot(snapshot)

        # Periodically consult tactical brain (every ~20 frames / 3Hz)
        desired_intent = None
        if self._frame_count % 20 == 0:
            summary = self.tactical_brain.summarize_window()
            decision = self.tactical_brain.fallback_tactical_rule(summary)
            desired_intent = decision.macro_intent

        # 60Hz deterministic safety gatekeeper evaluation
        action = self.gatekeeper.evaluate(snapshot, desired_intent=desired_intent)

        # Transmit concrete action back into Ikemen GO
        self.action_sender.send(action, frame=snapshot.frame)

        # Stream visual status to console
        if snapshot.frame % 30 == 0 or action.is_reaction:
            p1_pos = f"({snapshot.p1.pos.x:.1f},{snapshot.p1.pos.y:.1f})"
            p2_pos = f"({snapshot.p2.pos.x:.1f},{snapshot.p2.pos.y:.1f})"
            print(
                f"[F:{snapshot.frame:05d}] P1:{snapshot.p1.life:04d} {p1_pos} | "
                f"P2:{snapshot.p2.life:04d} {p2_pos} | "
                f"Dist:{snapshot.distance:.1f} | "
                f"SZ:{action.safe_back_zone} | "
                f"Action:{action.reaction_type or action.macro_intent.value} [{action.button.value}]"
            )

    async def start(self):
        self.running = True
        await self.receiver.start()
        print(f"=== FrameWhisper AI Agent Core Running ===")
        print(f"Telemetry Listening: UDP {self.telemetry_port}")
        print(f"Action Injecting:   UDP {self.action_port}")
        while self.running:
            await asyncio.sleep(0.5)

    async def stop(self):
        self.running = False
        await self.receiver.stop()
        self.action_sender.close()
        print("FrameWhisper AI Agent Core Stopped.")


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
