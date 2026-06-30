#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const SKILL_NAME = "marginalia";
const SOURCE_SKILL_DIR = path.join(PACKAGE_ROOT, "skills", SKILL_NAME);
const SOURCE_AGENT_FILE = path.join(PACKAGE_ROOT, ".agent");

function usage() {
  console.log(`Usage: marginalia-codex-skill [options]

Install the Marginalia skill into Codex.

Options:
  --codex-home <path>  Codex home directory. Defaults to $CODEX_HOME or ~/.codex.
  --agent-dir <path>   Also copy the repository .agent workflow file to <path>/.agent.
  -h, --help           Show this help message.
`);
}

function expandHome(inputPath) {
  if (!inputPath) return inputPath;
  if (inputPath === "~") return os.homedir();
  if (inputPath.startsWith("~/")) return path.join(os.homedir(), inputPath.slice(2));
  return path.resolve(inputPath);
}

function parseArgs(argv) {
  const options = {
    codexHome: process.env.CODEX_HOME || path.join(os.homedir(), ".codex"),
    agentDir: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === "-h" || arg === "--help") {
      options.help = true;
      continue;
    }

    if (arg === "--codex-home") {
      index += 1;
      if (!argv[index]) throw new Error("--codex-home requires a path");
      options.codexHome = argv[index];
      continue;
    }

    if (arg.startsWith("--codex-home=")) {
      options.codexHome = arg.slice("--codex-home=".length);
      continue;
    }

    if (arg === "--agent-dir") {
      index += 1;
      if (!argv[index]) throw new Error("--agent-dir requires a path");
      options.agentDir = argv[index];
      continue;
    }

    if (arg.startsWith("--agent-dir=")) {
      options.agentDir = arg.slice("--agent-dir=".length);
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  options.codexHome = expandHome(options.codexHome);
  options.agentDir = options.agentDir ? expandHome(options.agentDir) : null;
  return options;
}

function copySkill(sourceDir, targetDir) {
  if (!fs.existsSync(path.join(sourceDir, "SKILL.md"))) {
    throw new Error(`Skill source is missing SKILL.md: ${sourceDir}`);
  }

  fs.mkdirSync(path.dirname(targetDir), { recursive: true });
  fs.rmSync(targetDir, { recursive: true, force: true });
  fs.cpSync(sourceDir, targetDir, {
    recursive: true,
    filter: (sourcePath) => {
      const baseName = path.basename(sourcePath);
      return baseName !== "__pycache__" && baseName !== ".DS_Store" && !baseName.endsWith(".pyc");
    },
  });
}

function copyAgentFile(agentDir) {
  if (!fs.existsSync(SOURCE_AGENT_FILE)) {
    throw new Error(`Workflow source is missing: ${SOURCE_AGENT_FILE}`);
  }

  fs.mkdirSync(agentDir, { recursive: true });
  fs.copyFileSync(SOURCE_AGENT_FILE, path.join(agentDir, ".agent"));
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    usage();
    return;
  }

  const targetSkillDir = path.join(options.codexHome, "skills", SKILL_NAME);
  copySkill(SOURCE_SKILL_DIR, targetSkillDir);
  console.log(`Installed Codex skill: ${targetSkillDir}`);

  if (options.agentDir) {
    copyAgentFile(options.agentDir);
    console.log(`Installed Codex workflow file: ${path.join(options.agentDir, ".agent")}`);
  }

  console.log("Restart Codex to pick up new skills.");
}

try {
  main();
} catch (error) {
  console.error(`Failed to install Marginalia Codex skill: ${error.message}`);
  if (error.code === "EACCES" || error.code === "EPERM") {
    console.error("Run the installer from a shell that can write to your Codex home directory.");
  }
  process.exit(1);
}
