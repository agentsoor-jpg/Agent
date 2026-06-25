import { exec } from "child_process";

function run(cmd: string): Promise<{ stdout: string; stderr: string; code: number }> {
  return new Promise((resolve) => {
    exec(cmd, (error, stdout, stderr) => {
      resolve({
        stdout: stdout || "",
        stderr: stderr || (error ? error.message : ""),
        code: error && error.code ? error.code : 0
      });
    });
  });
}

async function main() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    console.log("ERROR: GITHUB_TOKEN is not defined in the environment.");
    process.exit(1);
  }

  console.log("Configuring git user details...");
  await run('git config --global user.name "agentsoor"');
  await run('git config --global user.email "agentsoor@gmail.com"');

  console.log("Staging files...");
  const addRes = await run("git add .");
  if (addRes.code !== 0) {
    console.log(`Add failed: ${addRes.stderr}`);
  }

  console.log("Creating commit...");
  const commitRes = await run('git commit -m "Final: pure execution system, render-ready, stable"');
  console.log(`Commit stdout: ${commitRes.stdout.trim()}`);
  if (commitRes.stderr) {
    console.log(`Commit stderr: ${commitRes.stderr.trim()}`);
  }

  // Get commit hash
  const hashRes = await run("git rev-parse HEAD");
  const hash = hashRes.stdout.trim();
  console.log(`Commit hash: ${hash}`);

  console.log("Pushing to GitHub...");
  const pushUrl = `https://${token}@github.com/agentsoor-jpg/Agent.git`;
  // We hide the token in logs
  const pushRes = await run(`git push ${pushUrl} main -f`);
  
  if (pushRes.code === 0) {
    console.log("Push Status: SUCCESS");
  } else {
    console.log("Push Status: FAILED");
    // Replace token with stars in any error messages to avoid leaking it
    const sanitizedStderr = pushRes.stderr.replace(token, "********");
    console.log(`Push stderr: ${sanitizedStderr}`);
  }
}

main();
