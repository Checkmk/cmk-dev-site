## fix error on missing sub command
<!--
type: bugfix
scope: all
affected: all
-->

previously the following error was visible when executed without sub command.

```
AttributeError: 'Namespace' object has no attribute 'func'
```

now the help is printed
