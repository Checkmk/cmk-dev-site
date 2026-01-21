## Print the status code and response in the API Exception
<!--
type: bugfix
scope: all
affected: all
-->

Previously if there was an error in the API call, the status code and response were not printed in the exception.
Now, the status code and response will be included in the API exception message for better debugging.
