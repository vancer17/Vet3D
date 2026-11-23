// Runs before local Codex tools, including when permission approvals are bypassed.
const http = require('node:http');
const chunks = [];
process.stdin.on('data', chunk => chunks.push(chunk));
process.stdin.on('end', () => {
  let finished = false;
  const finish = (allowed, confirmedSkills = []) => {
    if (finished) return;
    finished = true;
    const allowedOutput = confirmedSkills.length ? { hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      additionalContext: `The user explicitly accepted the Runtime credit confirmation for these skills in this task: ${confirmedSkills.join(', ')}. Do not ask for the same credit confirmation again.`,
    } } : {};
    process.stdout.write(JSON.stringify(allowed ? allowedOutput : {
      hookSpecificOutput: {
        hookEventName: 'PreToolUse', permissionDecision: 'deny',
        permissionDecisionReason: 'Credit consent was declined, cancelled, or unavailable. Stop the dependent work; do not bypass this check.',
      },
    }));
  };
  try {
    const request = http.request(process.argv[2], {
      method: 'POST', headers: { Authorization: `Bearer ${process.argv[3]}`, 'Content-Type': 'application/json' },
    }, response => {
      let body = '';
      response.on('data', chunk => { body += chunk; });
      response.on('end', () => {
        try {
          const result = JSON.parse(body);
          finish(response.statusCode === 200 && result.allowed === true, result.confirmedSkills);
        } catch { finish(false); }
      });
      response.on('error', () => finish(false));
    });
    // Deny before the host hook timeout; never let a timeout imply consent.
    request.setTimeout(550_000, () => request.destroy(new Error('Confirmation timed out')));
    request.on('error', () => finish(false));
    request.end(Buffer.concat(chunks));
  } catch { finish(false); }
});
