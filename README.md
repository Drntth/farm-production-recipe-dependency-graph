# Farm Production Graph

A graph-based dependency analysis system for farming and crafting production chains.

The project converts buildings, resources, and recipes into a weighted directed graph.
The generated graph can be used to analyze production dependencies, identify important nodes, and support optimized layout planning for complex production systems.

The initial target use case is modeling Hay Day production chains, but the architecture is designed to support other crafting and farming systems.

---

## Features

### Current features (v0.x)

- JSON based data input
- Recipe-driven dependency graph generation
- Weighted relationship calculation
- Directed graph representation
- Multiple export formats:
  - JSON
  - CSV
  - GraphML

### Planned features

- Interactive graph visualization
- Production chain analysis
- Dependency clustering
- Bottleneck detection
- Farm layout optimization
- Database-backed data management
- Web-based user interface

---

## Project Status

### Version 0.x - Python Graph Generator

The current implementation is a standalone Python application.

Architecture:

```text
JSON data
|
v
Python graph generator
|
v
Weighted dependency graph
|
+--> JSON export
+--> CSV export
+--> GraphML export
```

The purpose of version 0.x is:

- validate the data model
- test dependency calculation algorithms
- generate production graphs
- establish the foundation for future versions

---

## Version 1.0 - Full Application Platform

The planned 1.0 architecture will replace the standalone script with a full-stack application.

Architecture:

```text
TypeScript Frontend
|
v
Java Backend API
|
v
PostgreSQL Database
|
v
Graph calculation engine
```

Planned technologies:

| Component        | Technology      |
| ---------------- | --------------- |
| Frontend         | TypeScript      |
| Backend          | Java            |
| Database         | PostgreSQL      |
| API              | REST            |
| Graph processing | Backend service |

The goal of version 1.0 is to provide:

- persistent data storage
- user interface
- editable production graphs
- dynamic graph calculation
- visualization tools
- scalable architecture

---

## Architecture

### Current architecture (v0.x)

The current system is designed around three main layers:

```text
Data Layer
|
v
Graph Processing Layer
|
v
Export Layer
```

#### Data Layer

Stores:

- buildings
- resources
- recipes

Format:

- JSON

---

#### Graph Processing Layer

Responsible for:

- loading input data
- creating graph nodes
- generating relationships
- calculating connection weights

---

#### Export Layer

Generates:

- JSON
- CSV
- GraphML

The export layer is separated from graph generation to allow future integrations.

---

## Data Model

The system uses three main entities.

### Buildings

Production locations or entities.

Example:

```json
{
  "id": "dairy",
  "name": "Dairy",
  "type": "production"
}
```

### Resources

Raw materials and intermediate products.

Example:

```json
{
  "id": "milk",
  "name": "Milk",
  "type": "resource"
}
```

### Recipes

Every produced item is represented by a recipe.

A recipe contains:

- production building
- required inputs
- output resource
- production time

Example:

```json
{
  "id": "cream",
  "building": "dairy",
  "time": 30,
  "inputs": [
    {
      "resource": "milk",
      "amount": 1
    }
  ],
  "output": {
    "resource": "cream",
    "amount": 1
  }
}
```

### Graph Generation

The system creates a directed weighted dependency graph.

Example:

```text
Milk
 |
 v
Dairy
 |
 v
Cream
 |
 v
Ice Cream Machine
```

Connection strength is calculated from resource dependencies.

Example:

Butter requires:

- 2x Milk

Result:

Milk -> Dairy

weight +2

Multi-level dependencies are propagated through the production chain.

Example:

Ice Cream:

- 1x Milk
- 2x Cream

Cream requires:

- 1x Milk

Final Milk dependency:

1 + (2 \* 1)

= 3

### Export Formats

Supported:

#### JSON

Used for:

- web visualization
- application communication

#### CSV

Used for:

- spreadsheet analysis
- manual inspection

#### GraphML

Used for:

- Gephi
- yEd
- Cytoscape
- NetworkX

### Installation

Requirements:

- Python 3.11+

Install dependencies:

```bash
pip install -r requirements.txt
```

### Usage

Example:

```bash
python -m src.main
```

Output:

```bash
output/
├── graph.json
├── graph.csv
└── graph.graphml
```

### Project Structure

```bash
farm-production-recipe-dependency-graph/
├── data/
│   ├── buildings.json
│   ├── resources.json
│   └── recipes.json
├── src/
│   ├── models/
│   ├── loaders/
│   ├── graph/
│   └── exporters/
├── output/
├── tests/
├── requirements.txt
└── README.md
```

### Development

Development priorities:

- Finalize JSON data model
- Implement graph generation
- Implement dependency weighting
- Add exporters
- Validate graph quality with real production chains

### Roadmap

#### v0.1

- Initial Python project
- JSON data loading
- Basic graph generation

#### v0.5

- Advanced dependency calculation
- Improved weighting algorithms
- Graph analysis features

#### v1.0

- Java backend
- PostgreSQL database
- TypeScript frontend
- Persistent data management
- Interactive visualization

### License

MIT License

### Disclaimer

This project is an independent fan-made analysis tool.

Hay Day and related assets are properties of Supercell.
