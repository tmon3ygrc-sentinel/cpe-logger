# GRC Playground

**The sandbox for GRC pros to break things, test ideas, and learn by doing.**

Welcome to the GRC Playground! A space built for GRC folks who are tired of reading 500-page PDFs and want to actually do the thing. No more theory with no application. No more guessing how policy as code works. Just hands-on labs designed to teach you how to turn frameworks into something real.

This isn't your typical GRC content. We don’t do boring here.

---

## What You’ll Learn

- How to build and test real security controls  
- How tools like Conftest, Rego, and Trivy work in practice  
- How to use policy as code, CI/CD, and automation to reduce manual compliance work  
- How to actually map controls to technical implementations  
- How to stop saying “it depends” and start showing your work

---

## Who This Is For

- GRC pros who want to get more technical  
- Cybersecurity analysts who want to understand the “G” and “R” in GRC  
- Engineers who are being told to meet compliance requirements but don’t know what that means  
- Anyone who's been stuck Googling “how to policy-as-code” and ended up in a 40-tab rabbit hole  
- People who learn best by doing, not just by reading

---

## Labs

| Lab # | Title                                              | Description                                                                      | Category         |
|-------|----------------------------------------------------|----------------------------------------------------------------------------------|------------------|
| 1     | [Deny Public S3 Buckets](./Policy-As-Code/Lab%2001-Deny-Public-S3/README.md) | Use Rego and Conftest to prevent public S3 bucket configs                        | Policy-as-Code   |
| 2     | [Block Open Security Groups](./Policy-As-Code/Lab%2002-Block-Open-Security-Groups/readme.md) | Detect and block 0.0.0.0/0 open security groups using policy-as-code             | Policy-as-Code   |
| 3     | [IAM Policy Audits](./Policy-As-Code/IAM-Policy-Audits/readme.md) | Enforce IAM policies  | Policy-as-Code
| 4     | [MFA for Privileged Accounts](./Policy-As-Code/ia-2-1-enforcing-mfa-privileged-accounts/readme.md) | Enforce MFA for privileged accounts  | Policy-as-Code
| 5     | [Control Mapping for Beginners](./Control-Mapping/Lab%2001-Control-Mapping-for-Beginners/readme.md) | Learn how to connect NIST 800  | Control Mapping



More labs are in the works:  
Policy as Code, Continuous Monitoring, Evidence Automation, and anything else GRC needs but never gets taught.

---

## Start Here

New to GitHub? You’re not alone, and you’re not too late. Most GRC professionals weren’t handed a GitHub 101 course during onboarding. I get it.

### How to navigate this repo:
1. Scroll up to the **Labs** section.
2. Click any lab title to open the folder.
3. Inside each folder, open the `README.md` for step-by-step instructions.
4. Most labs run entirely in your browser using GitHub Codespaces. That means: no installs, no local setup, no excuses.

---

## Environment Setup (No Installs Needed)

This lab uses something called a **DevContainer**, which is like a pre-configured workspace with all the tools you need already set up and ready to go.

We designed this so you can focus on **learning how to write policies and test infrastructure**, not troubleshooting tool installations.

You’ll still be creating your own folders, files, and Rego policies from scratch the DevContainer just skips the annoying setup for:

- Terraform  
- Conftest  
- VS Code extensions

---

### New to GitHub or Codespaces?

No problem! You don’t need to install anything. Here’s how to get started:

1. **Fork this repo**  
   - Click the “Fork” button at the top right to create your own copy.

2. **Open it in GitHub Codespaces**  
   - On your forked repo, click the green “Code” button  
   - Select **“Open with Codespaces” → “New codespace”**

3. **Let it load**  
   - You’ll get a browser-based workspace that looks like VS Code  
   - All tools are already available, no installs needed

4. **Start the lab**  
   - You’ll follow the instructions to:
     - Create new folders and files
     - Write your own Terraform or policy code
     - Run `terraform plan` or `conftest test` in the built-in terminal

---

### Already using VS Code locally?

If you have the **Dev Containers extension** installed, just clone the repo and click “Reopen in Container” when prompted.

---

> You’re still doing the work. You’re just skipping the boring install part.

---

## Feedback Welcome

Have an idea for a new lab?  
Something break while testing?  
Want to say “this helped me actually get it”?

Open an issue, submit a PR, or yell at me nicely on [LinkedIn](https://www.linkedin.com/in/ashley-pearce). I’m always looking to make this more useful.

---

## Who Made This?

I’m a GRC nerd turned lab builder who got tired of seeing smart people struggle because no one showed them how this stuff actually works.

If you’re ready to move from checklist zombie to hands-on GRC wizard, you’re in the right place.

Follow along [on LinkedIn](https://www.linkedin.com/in/ashley-pearce) or contribute your own ideas for what we should build next.
