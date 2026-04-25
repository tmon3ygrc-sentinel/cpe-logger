
# Modern GRC Self-Assessment Checklist

This self-assessment is designed to help security, compliance, and engineering teams understand where they sit on the spectrum from traditional compliance to modern, automated GRC. It’s not just a scorecard, it’s a learning tool.

Whether you’re trying to reduce audit stress, integrate security into delivery, or just figure out why your policies live in a dusty PDF from 2018, this guide is your entry point.

---

## How to Use This

- Review each practice comparison and reflect honestly on your current state.
- Note where your team aligns with legacy vs. modern GRC practices.
- Use the real-world examples to spark conversation with your team.
- Apply the suggestions and resources to move toward more modern, automated workflows.

---

## Legacy vs. Modern GRC Practices

| Legacy Compliance Habit | Modern GRC Practice | Why It Matters | Real-World Example |
|--------------------------|---------------------|----------------|---------------------|
| Policies stored in Word docs or PDFs | Policies stored as Markdown in Git with version control | Storing policies in Git allows versioning, visibility, and engineering team engagement. You treat policies like living documentation, not static files. | Instead of emailing around “Policy_v7_FINAL_REALLY_FINAL.docx”, your policy lives in GitHub, with pull requests, commit history, and review comments. |
| Audit prep once a year | Continuous control monitoring and automated evidence collection | Real-time visibility gives you confidence in your security posture year-round, not just at audit time. | You use dashboards tied to logs and systems to prove controls are working, instead of compiling 100 screenshots the night before an audit. |
| GRC reviews happen after dev is done | GRC is integrated into product planning and development | GRC teams partner with engineering early, influencing architecture decisions and security by design. | During sprint planning, you identify controls that need to be met before work begins, removing surprises at deployment. |
| Manual screenshots as audit evidence | Evidence tied to source control, telemetry, or CI/CD pipelines | Manual screenshots are brittle and unverifiable. Automated evidence is reliable, timestamped, and scalable. | Every time code is committed or a pipeline runs, evidence is automatically generated and stored alongside the code. |
| Control reviews via email | Control reviews via Git pull requests with audit trail | Pull requests offer built-in collaboration, accountability, and traceability that email cannot provide. | A new control implementation is reviewed in a PR by security, with inline comments and approvals tracked permanently. |
| Risk register updated annually | Dynamic risk models and real-time dashboards | Annual updates miss critical shifts in risk posture. Continuous updates make risk management part of delivery. | As a new system is added or a threat emerges, your risk dashboard updates and reflects it within hours, not months. |
| Compliance owned by one or two people | Shared GRC responsibilities across teams | Compliance becomes more resilient and informed when product, engineering, and GRC collaborate. | Engineers write compliance-aware code, product owners consider impact levels, and GRC guides without blocking. |
| Evidence stored on desktops | Evidence lives in Git or cloud-native systems with access controls | Distributed storage is a security risk and a versioning nightmare. Centralized, auditable storage reduces risk and effort. | Your SSP lives in the same repo as your infrastructure code, versioned and access-controlled through Git. |
| Security and compliance are blockers | Security and compliance are enablers of speed and safety | Modern GRC helps teams ship faster, with fewer rework cycles and more trust from leadership and users. | Instead of delaying launches, security is built into the pipeline, reducing hotfixes and increasing uptime. |

---

## Scoring Yourself

This isn’t a test. It’s a snapshot of where you are and a compass for where you’re going.

**0–3 modern practices:**  
Your compliance program is likely reactive, high-stress, and siloed. There’s a lot of room to modernize, but also a big opportunity to make a visible impact.

**4–7 modern practices:**  
You’re in transition. Some practices are modern, others still rely on legacy methods. Focus on building automation, shifting GRC left, and engaging engineering early.

**8–10 modern practices:**  
You’re operating in the Modern GRC era. Keep evolving, document your approach, and start sharing it with others (and yes, that includes your AO).

---

## How to Use This With Your Team

- Run it as a team retrospective: “Where are we now, and what do we want to fix?”
- Use it to prep for audits or system changes: “What still relies on manual steps?”
- Share with leadership: “Here’s how we reduce risk, improve velocity, and build trust.”
- Use it in hiring or onboarding: “This is how we do GRC here.”

---

## Modernization Tips

1. **Start with Git**: Migrate your SSPs and policies into version-controlled markdown files. Treat them like code so they get reviewed, tracked, and collaboratively maintained.
2. **Automate evidence**: Use your CI/CD tools to collect and store evidence of control execution.
3. **Engage engineers**: Stop treating GRC like it lives outside delivery. Partner early. Use the tools and workflows they already love.
4. **Invest in dashboards**: Visibility builds trust with your team, your leadership, and your AO.
5. **Document and share**: Build playbooks that show your process. Teach others. That’s how you scale maturity.

---

## Resources

- [GRC Playground GitHub](https://github.com/grcplayground) – Labs, templates, and examples  
- [OpenControl](https://github.com/opencontrol) – Open-source framework for compliance as code  
- [Open Policy Agent (Rego)](https://www.openpolicyagent.org/) – Policy as code language for automation  
- [Conftest](https://www.conftest.dev/) – Use Rego to test your code, policies, and Kubernetes configs  
- [NIST 800-53 Controls](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final) – Know the controls before you try to automate them  

---

Created by [Ashley Pearce](https://www.linkedin.com/in/ashley-pearce-grc) | Founder, GRC Playground  
Want help modernizing your compliance approach? I’m building this out loud. Join me!
