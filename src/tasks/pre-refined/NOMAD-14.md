---
page_id: 2450fc11-d335-80bb-8b8e-c8757fe833c8
title: Processing tasks
ticket_id: NOMAD-14
stage: pre-refined
generated_at: 2025-08-04 07:48:18
---

We should update script now to check if there are tickets with status ‘Queued to run’ if yes then 

we should should move it to In progress, script should open claude code dangerously skiping permissions and execute prompt “Process all tasks from the task master, don’t stop unless you finish all of the tasks, after that close the app” 

Once it’s done we should move status to done 

Note if there’s more than one task queued, then take id of the first one from properties, find it’s task file in tasks/tasks/<id>.json and copy it as <parent_directory>/.ticketmaster/tasks/tasks.json

Additionally update script to update property Feedback on each step of the processing starting from refining so user will have simple information what is happening 