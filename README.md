# DSL Recommender for JetBrains MPS

## Overview

This project aims to develop a recommendation tool for Domain-Specific Languages (DSLs) integrated into the JetBrains Meta Programming System (MPS).

The tool helps developers discover and reuse DSL artifacts available in public repositories.

The recommendation system is based on a dataset generated through a GitHub mining pipeline that identifies and classifies DSL artifacts.

---

## Problem

Many DSL artifacts exist in public repositories but remain unknown or underutilized. Even when catalogued, identifying which DSL is suitable for a specific project can be difficult.

This leads to unnecessary reinvention of DSLs and limited reuse of existing language artifacts.

---

## Proposed Solution

This project proposes a DSL recommendation tool integrated with JetBrains MPS that allows developers to:

- search for existing DSLs
- explore metadata and repository information
- receive recommendations based on domain and technical characteristics

The system is initially based on the **RAS++ dataset** generated through repository mining.

---

## Architecture

The system follows a layered architecture composed of:

- Data Acquisition Layer
- Dataset Storage Layer
- Indexing Layer
- Recommendation Engine Layer
- API Layer
- Plugin Layer

Data flow:

GitHub Repositories  
→ Mining Pipeline  
→ DSL Classification (RAS++)  
→ PostgreSQL  
→ Elasticsearch  
→ Recommendation Engine  
→ REST API  
→ MPS Plugin

---

## Project Structure

```
dsl-recommender/
├── api/                  
│   ├── src/              
│   └── tests/            
│
├── mining-pipeline/     
│   └── src/
│
├── dataset/              
│   ├── schema/           
│   └── examples/         
│
├── plugin-mps/           
│   └── src/
│
├── docs/                 
│   ├── architecture.md
│   └── design-notes.md
│
├── scripts/              
│
├── tests/                
│
├── docker/              
│
├── .github/              
│
├── README.md            
├── LICENSE               
└── .gitignore           
```
---

## Technologies

- Python (API and mining pipeline)
- PostgreSQL (DSL metadata storage)
- Elasticsearch (search index)
- Java (MPS plugin)

---

## Roadmap

- [ ] Define DSL data model
- [ ] Implement DSL dataset storage
- [ ] Implement search API
- [ ] Implement recommendation engine
- [ ] Develop MPS plugin
- [ ] Integrate dataset refresh pipeline

---

## Status

Early-stage research and development.