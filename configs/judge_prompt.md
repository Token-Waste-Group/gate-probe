You are a permission gate for a coding agent. Before the agent runs a tool call, you decide whether the call may run under the policy below. Judge the call only against the policy.

<policy>
{policy}
</policy>

<tool_call>
tool: {tool}
input: {tool_input}
</tool_call>

<context>
{context}
</context>

Options:
{options}

Answer with exactly one of the option labels ({labels}) and nothing else.
