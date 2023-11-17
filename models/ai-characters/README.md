# AI Characters

## Why?

Creating your own AI character provides personalization, branding, emotional connection, user engagement, differentiation, and scalability benefits. It humanizes your brand, enhances user engagement, and sets you apart from competitors.

## How does it work?

To create an AI character using LLM (Language Model), you are going to follow these steps:

1. Define the character's personality and traits: 
Determine the characteristics, behavior, and tone of your AI character. Decide whether it should be friendly, professional, humorous, or any other desired personality traits.

2. Collect training data: 
Gather a dataset that includes examples of conversations and interactions that align with your AI character's personality. This dataset will be used to train the language model.

3. Fine-tune a language model: 
Utilize a pre-trained language model like GPT-3.5 Turbo and fine-tune it with your specific dataset. Fine-tuning involves training the model on your custom dataset to adapt it to your AI character's personality and style.

4. Implement conversational logic: 
Define the conversational logic and responses for your AI character. You can use if-else statements or other decision-making mechanisms to determine how your AI character should respond to different user inputs or queries.

5. Test and iterate through Naas Chat: 
Test your AI character by engaging in conversations and interactions in Naas Chat. Evaluate its responses and refine the conversational logic as needed. Iterate on the training process to improve the character's performance and accuracy.

## Get Started

### Google Sheets spreadsheet

To store the training dataset, we will use a Google Sheets spreadsheet. Follow these steps to get started:

1. Create a new Google Sheets spreadsheet.

2. Share the spreadsheet with naas by adding the email address "naas-share@naas-gsheets.iam.gserviceaccount.com".

Using Google Sheets for data storage allows for easy iteration and improvement of the dataset.

### Build Dataset

In the "build_dataset" folder, you will find notebooks that collect data from your profile and send it to the Google Sheets spreadsheet.

This data will be transformed into "question" and "answer" pairs, which will be used to train your future model.

You can use multiple templates to create your dataset in the spreadsheet.

### Create Your AI Character

#### Fine Tuning

In the "fine_tuning" folder, you will find notebooks that collect the dataset from Google Sheets and fine-tune your model. These templates will be used in the "__pipeline__.ipynb" file.

Additionally, the new models will be added to the Naas Workspace and a plugin will be created in Naas Chat.

#### Pipeline

The pipeline file, "__pipeline__.ipynb", executes the transformation from retrieving data from your spreadsheet to creating your chat plugin.
