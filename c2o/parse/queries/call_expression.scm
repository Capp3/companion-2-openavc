(call_expression
  function: [
    (identifier) @function.name
    (member_expression
      property: (property_identifier) @function.property) @function.member
  ]
  arguments: (arguments) @function.arguments) @call
