# GovSCH

**GovSCH** (Governance Schema) is an open‑source project that provides standardized, machine‑readable schemas for authoring and translating cybersecurity and AI governance documents.  
It delivers three schemas:  
- **Executive Orders Schema (eoschema)**: for U.S. presidential directives  
- **Framework Schema (frameworkschema)**: for cybersecurity and risk management frameworks  
- **Regulations Schema (regschema)**: for international data protection and privacy regulations  

These schemas bridge the gap between high‑level governance language and technical implementation, making policies easier to interpret, automate, and operationalize.

### **Quick Start**

Validate any governance document against a GovSCH schema in minutes.

#### **1. Clone the repository**
```bash
git clone https://github.com/newamericafoundation/GovSCH.git 
cd GovSCH
```

#### **2. Install dependencies**
For Python:
```bash
pip install jsonschema pyyaml
```

For Bash (optional):
```bash
npm install -g ajv-cli
```

#### **3. Validate a document**
Using Python:
```bash
python scripts/validate.py executiveorders/eoschema.json examples/eo.sample.json
```
Using Bash:
```bash
./scripts/validate.sh executiveorders/eoschema.json examples/eo.sample.json
```

#### **4. Try other schemas**
Swap in a different schema and sample:

```bash
python scripts/validate.py frameworks/frameworkschema.json examples/framework.sample.json
python scripts/validate.py regulations/regschema.json examples/regulation.sample.json
```

#### **5. Extend or contribute**
- Fork this repository and add new schema fields or examples.
- Submit a pull request with your improvements.

### Repository Structure
```
GovSCH/
├── schemas/
│   ├── executiveorders/
│   │   ├── eoschema.json
│   │   ├── eoschema.yaml
│   ├── frameworks/
│   │   ├── frameworkschema.json
│   │   ├── frameworkschema.yaml
│   ├── regulations/
│   │   ├── regschema.json
│   │   ├── regschema.yaml
├── examples/
│   ├── eo.sample.json
│   ├── framework.sample.json
│   ├── regulation.sample.json
├── scripts/
│   ├── validate.py
│   ├── validate.sh
├── docs/
│   ├── documentation.md
│   ├── methodology.md
├── VERSION
└── LICENSE
```

### Contributing
We welcome community contributions!

- Open an issue to suggest enhancements or report bugs.
- Fork and submit a pull request with changes to schemas, examples, or documentation.
- Share feedback to improve the schema for real‑world use cases.

### License
This project is open‑source and licensed under the MIT License.
See the LICENSE file for more details.

### Author
Developed by [Dr. Ibrahim Waziri Jr.](https://github.com/iwazirijr) as a New America [#STMIC Fellow](https://www.newamerica.org/our-people/ibrahim-waziri-jr/) and explored in depth in his report [GovSCH: An Open-Source Schema for Authoring Cybersecurity and AI Governance Documents.](https://www.newamerica.org/future-security/reports/govsch-an-open-source-schema/)

### Acknowledgments
Special thanks to Christina Morillo, Lauren Zabierek, Camille Stewart Gloster, Peter W. Singer, Bridget Chan, Olatunji Osunji, the 2025 #ShareTheMicInCyber cohort, and the New America teams whose guidance, feedback, and sponsorship made this work possible.
