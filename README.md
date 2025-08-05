# Template
Template for creating a new project in Python.
`black` and `isort` are used for formatting and sorting imports.


## Create a new project
Step-by-step [guide](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)

Or from open a terminal and run this command to create a new repository, which
- using the template `python_template`
- make it `private`
- owner is `neuronsolutionsorg` 

```bash
gh repo create neuronsolutionsorg/<PROJECT_NAME> \
  --template neuronsolutionsorg/python_template \
  --private
```