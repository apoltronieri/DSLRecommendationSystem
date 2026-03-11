# Architecture 

# Overview 

The archtecture applied in this tool is a layered architecture. 

![architecture_diagram](docs/images/diagrama_arq.drawio-2.png)


## Architecture Description 

- Data Acquisition Layer: All modules resposible for activities that range from mining GitHub to classifying the repositories found and standardizing them in the RAS++ template. 

-  Data Processing Layer: This layer prepares the collected data for storage and further processing. It includes the transformation and normalization processes required to convert the extracted information into a structured format compatible with the system's storage and indexing mechanisms.


- Dataset Storage Layer: This layer stores the DSL metadata extracted from the mining pipeline. A relational database (PostgreSQL) is used to persist DSL information, including repository metadata, domain classification, dependencies, and activity indicators.


- Indexing Layer: This layer is responsible for creating optimized search indexes that enable efficient queries over the DSL dataset. Elasticsearch is used to index DSL metadata and support fast keyword-based searches and filtering.


- API Layer: This layer exposes the system’s functionality through a REST API. It handles incoming queries, processes search requests, and communicates with the recommendation engine and indexing services.

- Plugin Layer: This layer provides the user interface within the JetBrains MPS environment. The plugin allows developers to search for DSLs, explore their metadata, and view relevant information directly from the development environment.
 

## Data Flow 

The system processes data through a pipeline that starts with repository mining and ends with DSL discovery within the MPS environment.

The overall flow is as follows:

GitHub repositories  
→ Mining pipeline  
→ RAS++ classification  
→ PostgreSQL storage  
→ Elasticsearch indexing  
→ Recommendation engine and API  
→ MPS plugin interface

This pipeline ensures that newly discovered DSL artifacts are periodically integrated into the dataset and made available for search and recommendation within the tool.