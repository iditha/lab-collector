# Test Assignment – Developing an App to Collect, Organize and Display Files

<!-- Assignment specification, translated faithfully from the Hebrew assignment PDF,
     keeping its structure and section numbers. Used by the senior-reviewer agent to
     check spec coverage. -->

## Introduction – Background and Lab Context

The lab carries out various runs (Runs). Each run is an independent but repeatable activity
performed in the lab.

Each run has its own unique name, and it produces various outputs in the form of repeatable files
that are saved in several folders and in different locations on the computer.

To manage and track the runs, all the files and outputs of each run must be gathered into a
uniform, defined folder structure, created for each run, that allows convenient access to them
in the future as well.

In addition to the files themselves, information describing the run and the circumstances in which
it was performed must be saved, including:

- The run's name.
- The name of the person who performed the run.
- A description of the run and the course of the activity performed.
- The run's results.
- Where the run was performed (lab or site).
- The software versions used to perform the run, or the Baseline of the relevant software versions.

The purpose of the app is to provide a convenient, organized solution for managing runs,
collecting their outputs, displaying them, and keeping a history of collection operations.

## 1. Goal of the Assignment

Develop an app whose job is to collect files from several sources on the computer, organize them
in a predefined folder structure, and give the user a convenient, intuitive interface for viewing
the collected files.

The app will also allow tracking collection operations performed in the past, including showing
the collection results and identifying faults.

## 2. Functional Requirements

### 2.1 Managing Run Details (Run)

The app will allow creating a new run and entering the following details for it:

- Run name: a unique identifier or name entered by the user.
- Run operator: the name of the person who performed the run.
- Run description: what was done and what happened during the run.
- Run results: a description of the results obtained.
- Run location: the lab or site where it was performed.
- Software versions / Baseline: details of the software versions and the baseline configuration
  used to perform the run.

The run details must be saved so that they are linked to all the files collected as part of it.

Separate access to each run must be possible, while keeping different runs separate.

### 2.2 File Collection

The app will scan several source folders, defined in advance, and collect files from them
according to different identification rules.

At least two types of identification rules must be supported (usually a combination of them):

**a. Identification by last modification time**
Retrieving the most recent files from a given folder (Last Modified).

**b. Identification by file name and type**
Finding files according to a defined file-name prefix (Prefix) and according to the file type
(extension).

It must be possible to define several sources and several identification rules.

The location and type of the files will be defined through some configuration file, which will be
saved by the app itself but can also be edited outside of it.

### 2.3 Organizing the Files

The collected files will be copied into a predefined folder structure.

Care must be taken that the files are placed in the appropriate folders according to the defined
collection rules, while associating them with the relevant run.

The outputs of different runs must be kept separate.

### 2.4 User Interface

A convenient, clear and aesthetic user interface must be developed that allows:

- Displaying the runs saved in the app.
- Displaying each run's details and the files associated with it.
- Displaying the files divided into categories or folders.
- Convenient access to each of the files.
- Opening files directly from the app, using the program appropriate to the file type.
- Access to the results of previous collection operations.
- Defining the app's input and output – which files to collect and where to put them.
  *(Translator's note: the original reads "לילדים" ("for children"), almost certainly a typo
  for "ללקט" ("to collect").)*

Emphasis should be placed on user experience (UX) and on clear presentation of information.

### 2.5 Collection History

The app will keep a history of the collection operations performed.

The user will be able to choose a previous collection operation and view its results. A
distinction must be made between:

- Different lab runs.
- Different collection operations performed for the same run.
- The times the collections were performed.

This way it will be possible to return to a specific run and check which files were collected for
it at each time.

### 2.6 Results Report and Fault Detection

At the end of each collection operation, the app will produce a summary report showing the
results of the operation.

The report will include, among other things:

- Whether the collection ended in full success.
- Whether all the expected files were collected.
- Whether the collection ended in partial success.
- Missing files.
- Files that could not be copied.
- Corrupt or unreadable files, as far as this can be detected.
- Relevant error messages and an explanation of the faults that occurred.

The report must be clear, concise and easy to read, and let the user quickly understand the state
of the collection.

### 2.7 Contacting a Remote Computer

Besides collecting the files to a remote computer, a UDP message must also be sent over Ethernet to
a remote computer whose IP is defined in the configuration file.

## 3. Technology and Development Environment

There is no restriction on the programming language, development environment or technologies that
may be used.

External tools and resources may be used, including:

- Various AI tools.
- GitHub.
- Open-source libraries and code.
- Automated development tools.
- Consulting with other people.

The goal is to let you choose the most suitable way to implement the solution.

## 4. Schedule and Deliverables

The assignment must be completed and submitted within three days of receiving it.

Required deliverables:

- A working app that can be run and demonstrated on a regular PC, connected over a network to
  other computers.
- The full source code.
- Installation and run instructions.
- A short explanation of the solution's structure and how it works.
- A list of the tools, technologies and aids used, and in particular AI tools.

## 5. Presenting the Solution and Defending the Implementation

After the assignment is submitted, a meeting will be held in which you will be asked to present
the app and explain how it was implemented.

The meeting will also test your familiarity with the code and with the solution you developed.

You may be asked, among other things:

- To explain the app's architecture.
- To explain how files are identified and collected.
- To show how errors are handled.
- To explain how run details and collection history are saved.
- To show parts of the code and explain their role.
- To make a small change to the app according to a requirement given during the meeting.

Important to emphasize:

Using AI tools and external resources is allowed and even encouraged. However, the presentation
will test your personal understanding of the solution, how it works and the code you wrote.

It is not enough to show an app that works; you must be able to explain the implementation,
understand the choices made, and demonstrate command of the solution.

## 6. Evaluation Criteria

The evaluation will be based on several aspects:

| Aspect | What will be tested |
|---|---|
| Meeting the requirements | Implementation of the requested functionality |
| Run management | Saving the run details and linking the files to it |
| Design and architecture | The structure of the solution and its division into components |
| Implementation quality | Code readability, maintainability and reliability |
| Error handling | Detecting, reporting and dealing with faults |
| User interface | Convenience, aesthetics and user experience |
| Independence and understanding | Ability to explain the solution and defend the choices made |
| Use of AI | Ability to use AI tools wisely and efficiently |

Thank you and good luck
