#!/bin/bash
# test_webhook.sh — stuur een testbericht naar de server
curl -X POST http://127.0.0.1:5000/signal-webhook \
  -H "Content-Type: application/json" \
  -d '{"envelope":{"source":"+233537790204","dataMessage":{"message":"Ik heb erge hoofdpijn, wat moet ik doen?"}}}'
