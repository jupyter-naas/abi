![Naas.ai - Open Source Data Platform](assets/project_logo.png)

# Naas Data Product Framework

Naas is a low-code open source data platform that enables anyone working with data, including business analysts, scientists, and engineers, to easily create powerful data products combining automation, analytics, and AI from the comfort of their Jupyter notebooks. With its open source distribution model, Naas ensures visible source code and versioning, and allows you to create custom logic.

The platform is structured around three low-code layers:

- **Templates** enable users to create automated data jobs in minutes, and are the building blocks of data products.
- **Drivers** act as connectors, allowing you to push and/or pull data from databases, APIs, and machine learning algorithms, and more.
- **Features** transform Jupyter notebooks into a production-ready environment, with features such as scheduling, asset sharing, and notifications.

You can try Naas for free using Naas Cloud, a stable environment that runs in your browser.

## **How Does It Work?**

This repository is a boilerplate for anyone who wishes to develop a data product using Naas. It is structured as follows:

- The **`/assets`** folder stores any PNG, JPG, GIF, CSV, diagrams, or slides related to the documentation of the product.
- The **`/inputs`** folder stores the parameters and any other files needed (data, referential) to run the files in the **`/models`** folder.
- The **`/models`** folder stores any files that transform inputs into outputs (notebook, Python, SQL files)
    - The **`__pipeline__.ipynb`** file is used to automate the model selection process, ensuring that the most accurate model is always used for a given task.
    
- The **`/outputs`** folder stores all the files that would be exposed outside of the Naas server.
- The **`/tests`** folder stores all tests to be performed before production.
- The **`/utils`** folder stores all common functions used across files.
- The **`requirements.txt`** file lists all the packages and dependencies.
- The **`setup.ipynb`** file runs the product on a Naas server.

## What Are The Benefits?

Some benefits of the Naas Data Product Framework are:

- **Low-code approach**: The low-code nature of the Naas platform makes it easy for anyone, regardless of their technical background, to create powerful data products.
- **Open source**: The open source distribution model of Naas ensures visible source code and versioning, and allows you to create custom logic.
- **Jupyter integration**: Naas integrates seamlessly with Jupyter notebooks, allowing you to create data products from the comfort of your familiar environment.
- **Versatility**: With its templates, drivers, and features, Naas is highly versatile and enables you to build almost anything.
- **Cloud-based**: Naas Cloud, the stable environment provided by Naas, allows you to access the platform from anywhere with an internet connection.

Overall, the Naas Data Product Framework is a powerful tool for anyone looking to create data products that combine automation, analytics, and AI.

## Why a Data Product Development Framework Like Naas is Necessary?

Just as web development frameworks like React.js help developers create web applications more efficiently by providing a set of standardized tools and components, data product development frameworks like Naas help data scientists and engineers create data products more efficiently by providing a set of standardized tools and components specifically designed for data processing, analytics, and AI.

Some specific benefits of using a data product development framework like Naas include:

- **Standardized structure**: A data product development framework provides a standardized structure for organizing and developing data products, which can make it easier to develop, maintain, and scale data products.
- **Pre-built components**: A data product development framework includes a set of pre-built components, such as data connectors and data transformation tools, which can save time and effort compared to building these components from scratch.
- **Integration with other tools**: A data product development framework typically integrates with other tools and technologies commonly used in the data world, such as Jupyter notebooks and machine learning libraries, which can make it easier to build and deploy data products.
- **Collaboration and sharing**: A data product development framework can make it easier for multiple people to collaborate and share data products within an organization, as it provides a consistent framework for development and documentation.

Overall, a data product development framework like Naas can provide a number of benefits to data scientists and engineers, including improved efficiency, integration with other tools, and the ability to collaborate and share data products within an organization.

## How Data Products And Asociatedd Contracts Can Create More Trust From End-User?

A data product framework can help with defining data contracts and creating trust with end users in several ways:

- **Standardized structure**: A data product framework provides a standardized structure for organizing and developing data products, which can make it easier to define clear and consistent data contracts. For example, if a data product is built using a framework that specifies how input and output data should be structured and documented, it can be easier for end users to understand how the data product works and what they can expect from it.
- **Transparency**: Many data product frameworks are open source, which means that the source code is visible and can be reviewed by anyone. This transparency can help build trust with end users, as they can see exactly how the data product works and how it processes their data.
- **Auditability**: A data product framework can also provide tools and processes for auditing and reviewing data products, which can help ensure that they are reliable and accurate. This can be especially important for data products that are used in mission-critical applications, as end users need to be confident that the data products are reliable and trustworthy.

Overall, a data product framework can help create trust with end users by providing a standardized and transparent structure for developing data products, and by providing tools and processes for auditing and reviewing the products to ensure their reliability.

## **About This Repository**

This Data Product Framework repository is a boilerplate to create powerful Data Products in your company. To get started:

1. Create an organization on GitHub.
2. Use this template to kickstart your Data Product.
3. Start bringing value to your company.

## **Built With**

- Jupyter Notebooks
- Naas

## **Documentation**

### **Prerequisites**

- Create an account on naas.ai

### **Installation**

Follow the steps in the **`settings.ipynb`** notebook.

## **Roadmap**

- V0: Simple boilerplate with Naas pipeline feature
- V1: Add Naas space feature to create powerful dashboard

## **Support**

If you have problems or questions, please open an issue and we will try to help you as soon as possible.

## **Contributing**

Contributions are welcome. If you have a suggestion that would make this better, please fork the repository and create a pull request. You can also simply open an issue with the tag "enhancement". Don't forget to give the project a star.

To contribute:

1. Create an account on naas.ai.
2. Clone the repository on your machine.
3. Create a feature branch.
4. Commit your changes.
5. Push to the branch.
6. Open a pull request.


## Product Owners

* [Florent Ravenel](https://www.linkedin.com/in/florent-ravenel/) - florent@naas.ai
* [Jeremy Ravenel](https://www.linkedin.com/in/ACoAAAJHE7sB5OxuKHuzguZ9L6lfDHqw--cdnJg/) - jeremy@naas.ai
* [Maxime Jublou](https://www.linkedin.com/in/maximejublou/) - maxime@naas.ai


## Acknowledgments

* [Awesome Notebooks](https://github.com/jupyter-naas/awesome-notebooks)
* [Naas Drivers](https://github.com/jupyter-naas/drivers)
* [Naas](https://github.com/jupyter-naas/naas)
* [Naas Data Product](https://github.com/jupyter-naas/naas-data-product)


## Legal

This project is licensed under AGPL-3.0