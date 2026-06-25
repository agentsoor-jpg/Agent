import http from "http";
import fs from "fs";
import path from "path";

// Helper to make POST request
function postJson(url: string, body: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const postData = JSON.stringify(body);
    
    const req = http.request(
      {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || 80,
        path: parsedUrl.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => {
          data += chunk;
        });
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve(data);
          }
        });
      }
    );
    
    req.on("error", reject);
    req.write(postData);
    req.end();
  });
}

// Helper to make GET request
function getJson(url: string): Promise<any> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(data);
        }
      });
    }).on("error", reject);
  });
}

async function runTest() {
  console.log("=========================================");
  console.log("STARTING END-TO-END META-AGENT TEST");
  console.log("=========================================");

  const goal = "Create a simple Python file main.py that prints Hello World, then run it";
  
  console.log(`Sending execution request to Meta-Agent. Goal: "${goal}"`);
  const startRes = await postJson("http://localhost:3000/api/meta/execute", { goal, mode: "safe" });
  
  if (!startRes || !startRes.workflow_id) {
    console.error("FAILED to initiate workflow. Response:", startRes);
    process.exit(1);
  }

  const workflowId = startRes.workflow_id;
  console.log(`Workflow instantiated successfully! ID: ${workflowId}`);
  console.log("Pending steps in plan:", JSON.stringify(startRes.plan, null, 2));

  // Polling loop
  console.log("\nPolling workflow status in execution engine...");
  let completed = false;
  let workflowDetails: any = null;
  const maxAttempts = 20;
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    await new Promise((r) => setTimeout(r, 1000));
    const workflows = await getJson("http://localhost:3000/api/meta/workflows");
    
    workflowDetails = Array.isArray(workflows) 
      ? workflows.find((w: any) => w.id === workflowId)
      : null;

    if (workflowDetails) {
      console.log(`Attempt ${attempt}/${maxAttempts}: Status = ${workflowDetails.status}`);
      if (workflowDetails.status === "completed" || workflowDetails.status === "failed") {
        completed = true;
        break;
      }
    } else {
      console.log(`Attempt ${attempt}/${maxAttempts}: Workflow details not found in API response yet.`);
    }
  }

  if (!completed) {
    console.error("Test timed out before workflow completion.");
  }

  console.log("\n=========================================");
  console.log("TEST RESULTS & EVIDENCE ANALYSIS");
  console.log("=========================================");

  // A) PHYSICAL FILE VERIFICATION
  const absoluteWorkspacePath = path.resolve(process.cwd(), "workspace_run");
  const targetFilePath = path.join(absoluteWorkspacePath, "main.py");
  
  console.log("A) PHYSICAL FILE CHECK:");
  if (fs.existsSync(targetFilePath)) {
    console.log(`[PASS] File exists at: ${targetFilePath}`);
    const fileContents = fs.readFileSync(targetFilePath, "utf8");
    console.log("--- File Content Start ---");
    console.log(fileContents.trim());
    console.log("--- File Content End ---");
  } else {
    console.log(`[FAIL] File does not exist at expected path: ${targetFilePath}`);
  }

  // B) EXECUTION OUTPUT VERIFICATION
  console.log("\nB) EXECUTION STDOUT CHECK:");
  if (workflowDetails && workflowDetails.plan) {
    const runStep = workflowDetails.plan.find((s: any) => s.action === "run_command");
    if (runStep) {
      console.log(`Executed Command: ${runStep.command || runStep.file || "python main.py"}`);
      console.log("--- Console Output Logs ---");
      console.log(runStep.output || "No output returned.");
      console.log("----------------------------");
      
      const cleanOutput = (runStep.output || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      const containsHelloWorld = cleanOutput.includes("helloworld");
      if (containsHelloWorld) {
        console.log("[PASS] Output correctly contains 'Hello World'!");
      } else {
        console.log("[FAIL] 'Hello World' was not found in the step output.");
      }
    } else {
      console.log("[FAIL] Could not find a run_command step in the workflow execution plan.");
    }
  }

  // C) TRUST / INTEGRITY CHECK
  console.log("\nC) EXECUTION ENGINE INTEGRITY:");
  if (workflowDetails) {
    const writeStep = workflowDetails.plan.find((s: any) => s.action === "write_file");
    if (writeStep && writeStep.qualityScore !== undefined) {
      console.log(`[PASS] Execution driven by actual model plan & Quality Manager audit (QA Score: ${writeStep.qualityScore * 100}%).`);
    } else {
      console.log("[WARNING] No QA Quality Score verification. Gemini fallback may have occurred.");
    }
  }

  // E) STEP-BY-STEP WORKFLOW SEQUENCE LOG
  console.log("\nE) STEP-BY-STEP PROGRESSION LOGS:");
  if (workflowDetails && workflowDetails.plan) {
    workflowDetails.plan.forEach((step: any) => {
      console.log(`Step ${step.step}: [${step.action.toUpperCase()}] executed on [${step.executor}]`);
      console.log(`  File: ${step.file || "N/A"}`);
      console.log(`  Status: ${step.status}`);
      if (step.output) console.log(`  Output: ${step.output.trim()}`);
      if (step.error) console.log(`  Error: ${step.error}`);
    });
  }

  console.log("\n=========================================");
}

runTest().catch((err) => {
  console.error("Test failed with exception:", err);
});
