<!-- 85014dc6-0241-4438-b060-eb980066aa5e 90017e22-1803-45be-ad09-877a95073292 -->
# Fix PDF Text Highlighting Using PDF.js Best Practices

## Problem

Current highlighting fails because:

1. Trying to match PyPDF2-extracted chunk text with PDF.js-extracted text (different extraction methods)
2. Complex text normalization that still fails due to spacing differences
3. Incorrect coordinate calculations from transform matrix

## Solution: Use PDF.js Standard Approach

### Standard PDF.js Highlighting Pattern:

1. Get text items from `getTextContent()` - each item has `str` and `transform` matrix
2. Match text items directly by searching item strings (not reconstructed full text)
3. Use transform matrix correctly: `[a, b, c, d, e, f]` where:

- `e` (transform[4]) = X position
- `f` (transform[5]) = Y position from bottom
- `a` (transform[0]) = horizontal scale
- `d` (transform[3]) = vertical scale (height)

4. Convert coordinates: `y = viewport.height - transform[5] - height`

## Implementation Plan

### File: `ui/components/DocumentViewer.tsx`

**Changes:**

1. **Simplify text matching**: Instead of reconstructing full text and matching, iterate through text items and match each item's `str` property directly
2. **Use key phrase matching**: Extract 3-5 key words from search text and find items containing those words
3. **Fix coordinate calculation**: 

- Use `item.transform[4]` for X (already correct)
- Use `item.transform[5]` for Y from bottom
- Calculate width from `transform[0] * item.str.length` or use item width if available
- Calculate height from `Math.abs(transform[3])`
- Convert Y: `viewport.height - transform[5] - height`

4. **Group by line**: Group items with same Y position (within tolerance) to create line rectangles
5. **Handle both clause and text-based highlighting**: Use clause text or highlightText, extract key phrases, match items

### Key Improvements:

- Match text items individually (not reconstructed text)
- Use simple word matching instead of complex normalization
- Correct transform matrix usage
- Proper coordinate conversion
- Better handling of multi-line highlights

## Testing

Test with:

- "What is the term of the Fanuc NDA?" (clause-based)
- "What is the effective date for Fanuc?" (text-based, no clause)
- "What is the governing law for Fanuc?" (clause-based)

Expected: Highlights appear on correct text sections in PDF

### To-dos

- [ ] Fix chunk text deduplication in clause extractor
- [ ] Add document_id filtering to search backends
- [ ] Deduplicate citations in answer service
- [ ] Fix PDF highlighting to match chunk text in PDF.js