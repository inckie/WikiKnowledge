---
categories: []
created: '2026-06-20T02:02:12.540707+00:00'
id: overview
modified: '2026-06-20T02:02:12.540732+00:00'
tags:
- documentation
title: WikiKnowledge overview
type: leaf
---

# WikiKnowledge Graph Construction and Question Answering System

## Overview

### Background

Why Wikipedia thrives while WikiBooks does not?
Writing a book, on the other hand requires building a logical structure, where each next chapter is based on the previous one. This is a much more difficult task, and it is not surprising that WikiBooks has not gained as much traction as Wikipedia.
Take a look on a typical (western) text book:
- it starts with a brief table of contents, which is a graph of the book's structure
- then each chapter in the table of content has a more detailed outline, which is a subgraph of the chapter's structure
- every part of the book has an introduction, which is a summary of the content and its relation to the rest of the book
- then each chapter also follows same fractal structure: it starts with a preface where main concepts of the chapter are introduced, then the chapter is divided into sections, each section has its own introduction and summary, and so on
- every chapter follow scientific method: it starts with a problem statement, then it describes the method to solve the problem, and finally it presents the results and conclusions
- material of the every chapter is accompanied by examples, exercises, and references to other chapters and external sources
- each chapter is a node in the graph, and the edges represent the logical flow of information

Wikipedia is a tool to organize assorted pieces of knowledge in a structured way. It has a number of tools to manage the chaos that arises from the absence of the "architect", a single person or a collective that is responsible for the structure of the book. Two key tools are wiki anchors themselves, and "What links here" page. For example, it has categories, which are a way to group related articles together, and it has templates, which are a way to standardize the presentation of information across articles. However, these tools are not enough to create a coherent structure for the knowledge in Wikipedia.
This difference makes it possible to use Wikipedia to get information on a specific topic, but does not allow to learn a new topic from scratch. For example, if you want to learn about machine learning, you can read the Wikipedia article on machine learning, but it will not give you a comprehensive understanding of the topic. You will need to read multiple articles and piece together the information yourself. On the other hand, if you have a well-structured book on machine learning, you can read it from start to finish and get a comprehensive understanding of the topic.

### Project goal

This project provides a means to build a hierarchical "fractal" knowledge graph over the information distributed among separate markdown files. It uses wiki tools: anchors, categories and reverse links to create a graph of the knowledge, utilizes AI to create summaries for the multilevel "superstructure", that guides the reader through the knowledge, and allows to quickly get a gasp of a specific topic, and dive in deeper if needed. The project also provides a question answering system, which allows to ask questions about the knowledge in the graph, and get answers based on the information in the graph.

### Data organization

Knowledge is stored in "leaf" articles, that has wiki tags and categories anchors to make these articles indexable. For each category there is a "superstructure" article, which is a summary of the category and its relation to other categories. The superstructure articles are also organized in a hierarchical way, where each superstructure article has a parent superstructure article, and so on. The top-level superstructure article is the root of the graph, and it provides an overview of the entire knowledge graph.
Every article can be part of the many categories, so there is no strict hierarchical structure, but it's still always possible to go "up".
Combinations of different categories can also have their own superstructure articles, which are summaries of the combined knowledge of the categories. For example, if there are two categories "Rigid body dynamics" and "Computer simulation", there can be a superstructure article "Rigid body dynamics in computer simulation", which is a summary of the knowledge in both categories and their relation to each other, that will explain different approaches to building physics simulation engines.

On the physical level, information can be [[storage-abstraction|stored]] in one of the two ways: markdown files and index file, that can be rebuilt from scratch at any time. Other option is NoSQL like MongoDB with categories and external references separated to the indexable fields.

Typical update cascading looks like this: leaf article is updated, which triggers update of the superstructure article of the category, which triggers update of the parent superstructure article, and so on, up to the root superstructure article. This way the entire graph is always up to date, and the reader can always get a comprehensive understanding of the topic by reading the superstructure articles, and then dive into the leaf articles for more details if needed.

Rewriting of the superstructure articles is done by AI, which allows to quickly update the entire graph without much manual work, but they can have specially marked sections that are supported by the humans. Human written part acts as a preface in the explanations above that defines the main concepts and the structure of the knowledge, while AI written part is summary of the articles with references to go deeper. This way the human can focus on the "architect" part of the book, while AI can take care of the "content" part of the book.

There is also visualization of the graph, which allows to see the structure of the knowledge and navigate through it. The visualization can be done using tools like D3.js or Graphviz, and it can be integrated into the web interface of the project.