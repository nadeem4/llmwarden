"""Tags, attempt records, a report, and your own sink. Runs offline on FakeBackend.

Replace FakeBackend with a real model name and key to see real numbers. Everything
else stays the same: tags set at the request boundary apply to every call inside,
every attempt is recorded (retries included), and the report groups by any tag.
"""

import llmwarden as lw
from llmwarden.backends import FakeBackend
from llmwarden.backends.fake import FakeRateLimit, reply
from llmwarden.types import Usage

CUSTOMERS = ("acme", "globex")

# Scripted backends: for each customer the planner is rate limited once, then answers.
planner_script = [FakeRateLimit("slow down"), reply("plan", usage=Usage(120, 40))] * len(CUSTOMERS)
writer_script = [reply("draft", usage=Usage(300, 900))] * len(CUSTOMERS)

planner = lw.model(
    "fake/planner",
    api_key="demo-key",
    backend=FakeBackend(planner_script),
    price=lw.Price(input_per_million=2.0, output_per_million=10.0),
    retry=lw.Retry(attempts=3, base=0.0, cap=0.0),
)
writer = lw.model(
    "fake/writer",
    api_key="demo-key",
    backend=FakeBackend(writer_script),
    price=lw.Price(input_per_million=2.0, output_per_million=10.0),
)


# Your own sink: any callable that takes an AttemptRecord. Send it to your database,
# your billing system, or a log line. Records hold no prompt, no reply and no key.
def to_stdout(record: lw.AttemptRecord) -> None:
    print(
        f"  attempt {record.attempt} {record.model:<8} {record.outcome:<14}"
        f" cost={record.cost_usd} tags={dict(record.tags)}"
    )


lw.observe.add(to_stdout)

for customer in CUSTOMERS:
    # Tags set here apply to every call inside the block, however deep.
    with lw.tags(request=f"req-{customer}", customer=customer):
        plan = planner.complete(user="plan it", tags={"agent": "planner"})
        draft = writer.complete(user=plan.text, tags={"agent": "writer"})

print()
for row in lw.report(group_by=["customer", "agent"]):
    print(
        f"{row.group['customer']:<7} {row.group['agent']:<8}"
        f" calls={row.calls} attempts={row.attempts} failures={dict(row.failures)}"
        f" cost=${row.cost_usd:.4f} wasted=${row.wasted_usd:.4f}"
    )

# OpenTelemetry: pip install "llmwarden[otel]", then one line and every attempt is a span
# in Grafana, Jaeger, Langfuse, Phoenix or Datadog:
#
#   from llmwarden.observe.otel import OtelSink
#   lw.observe.add(OtelSink())
