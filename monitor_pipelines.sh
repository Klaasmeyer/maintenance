#!/bin/bash
# Pipeline monitoring script - tracks both Floydada and Wink pipeline progress

FLOYDADA_LOG="/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/b1f3a50.output"
WINK_LOG="/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/bbf6ec0.output"

echo "=========================================================================="
echo "Pipeline Monitor - Checking Progress"
echo "=========================================================================="
echo

echo "Floydada Pipeline Status:"
echo "-------------------------"
if [ -f "$FLOYDADA_LOG" ]; then
    # Check for completion indicators
    if grep -q "✅ Pipeline complete" "$FLOYDADA_LOG" 2>/dev/null; then
        echo "✅ COMPLETE"
        tail -15 "$FLOYDADA_LOG" | grep -E "(✅|saved to|Total:)"
    elif grep -q "❌" "$FLOYDADA_LOG" 2>/dev/null; then
        echo "❌ ERROR DETECTED"
        tail -10 "$FLOYDADA_LOG"
    else
        echo "⏳ RUNNING"
        tail -5 "$FLOYDADA_LOG" | grep -E "(Processing|Stage|✓)" || echo "  Still loading..."
    fi
else
    echo "❓ Log file not found"
fi

echo
echo "Wink Pipeline Status:"
echo "---------------------"
if [ -f "$WINK_LOG" ]; then
    # Check for completion indicators
    if grep -q "✅ Pipeline complete" "$WINK_LOG" 2>/dev/null; then
        echo "✅ COMPLETE"
        tail -15 "$WINK_LOG" | grep -E "(✅|saved to|Total:)"
    elif grep -q "❌" "$WINK_LOG" 2>/dev/null; then
        echo "❌ ERROR DETECTED"
        tail -10 "$WINK_LOG"
    else
        echo "⏳ RUNNING"
        tail -5 "$WINK_LOG" | grep -E "(Processing|Stage|✓)" || echo "  Still loading..."
    fi
else
    echo "❓ Log file not found"
fi

echo
echo "=========================================================================="
echo "Output Files Generated:"
echo "=========================================================================="
echo
echo "Floydada outputs:"
ls -lth projects/floydada/outputs/ 2>/dev/null | head -5 || echo "  (none yet)"
echo
echo "Wink outputs:"
ls -lth projects/wink/outputs/ 2>/dev/null | head -5 || echo "  (none yet)"
echo
echo "=========================================================================="
echo "To check full logs:"
echo "  Floydada: tail -f $FLOYDADA_LOG"
echo "  Wink:     tail -f $WINK_LOG"
echo "=========================================================================="
