import http from "http";

const req = http.request(
  {
    hostname: "localhost",
    port: 3000,
    path: "/api/meta/github/push",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  },
  (res) => {
    let data = "";
    res.on("data", (chunk) => {
      data += chunk;
    });
    res.on("end", () => {
      console.log("STATUS:", res.statusCode);
      console.log("RESPONSE:", data);
    });
  }
);

req.on("error", (e) => {
  console.error("Error triggering push:", e.message);
});

req.end();
