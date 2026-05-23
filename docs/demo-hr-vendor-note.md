# Vendor Note: Recruiting Assistant Model And Operations

## System Description

The recruiting assistant uses a language model to summarize CVs and application answers. It also uses a scoring model to compare candidate materials against job requirements and produce ranking signals for recruiters.

## Model Inputs

The model receives candidate-submitted application materials, extracted CV text, job descriptions, screening questions, and recruiter-provided role criteria. The vendor states that special-category data should not be intentionally used for scoring, but the current note does not prove that all proxy variables have been assessed.

## Model Outputs

The system produces generated text summaries, skill extraction results, fit scores, ranking recommendations, and reasons for recruiter review. The vendor describes the output as decision support and says the customer remains responsible for final hiring decisions.

## Training And Validation

The vendor says the scoring model was trained using historical recruiting records and job requirement labels. The vendor has not yet provided a complete validation report, subgroup performance analysis, or bias testing evidence for the customer's EU hiring context.

## Human Oversight

Recruiters can review each recommendation and can choose a different action from the model recommendation. The vendor note does not define minimum review time, override documentation, candidate notice, or escalation requirements.

## Logging

The system logs input document identifiers, generated summaries, ranking scores, recruiter actions, overrides, timestamps, and model version. Log retention and post-deployment monitoring responsibilities are not fully specified.

## Provider And Deployer

The vendor supplies the model and API. The customer configures the workflow and uses the assistant in its own hiring process. Contractual allocation of provider and deployer responsibilities is still under review.
