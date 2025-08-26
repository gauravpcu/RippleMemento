/**
 * Frontend Diff Display (diff-render.js)
 * Based on new's approach using jsdiff library
 * 
 * Features:
 * - Lines vs Characters vs JSON diff modes
 * - Visual highlighting with <del> (removed) and <ins> (added) tags
 * - Interactive "jump to next difference" functionality
 * - Real-time diff switching without server requests
 * - MD5-based change detection
 * - Tab preservation for tabular data (configurable)
 * 
 * Tab Handling:
 * - "Preserve Tabs" option maintains tab characters for proper column alignment
 * - When enabled, tabs are preserved even when "Ignore Spaces" is checked
 * - Essential for tabular data like CSV, TSV, or formatted tables
 * - Uses CSS tab-size: 4 for consistent display across browsers
 */

class DiffRenderer {
    constructor() {
        this.currentDiffType = 'diffLines';
        this.diffResults = [];
        this.currentDiffIndex = 0;
        this.changeCount = 0;
        this.ignoreWhitespace = false;
        this.preserveTabs = true; // Default to preserving tabs for tabular data
    }

    // Initialize the diff renderer
    init() {
        this.setupEventListeners();
        this.renderDiff();
    }

    // Set up all event listeners
    setupEventListeners() {
        // Diff type radio buttons
        document.querySelectorAll('input[name="diff_type"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.currentDiffType = radio.value;
                this.renderDiff();
            });
        });

        // Ignore whitespace checkbox
        const ignoreWhitespaceCheckbox = document.getElementById('ignoreWhitespace');
        if (ignoreWhitespaceCheckbox) {
            ignoreWhitespaceCheckbox.addEventListener('change', () => {
                this.ignoreWhitespace = ignoreWhitespaceCheckbox.checked;
                this.renderDiff();
            });
        }

        // Preserve tabs checkbox
        const preserveTabsCheckbox = document.getElementById('preserveTabs');
        if (preserveTabsCheckbox) {
            preserveTabsCheckbox.addEventListener('change', () => {
                this.preserveTabs = preserveTabsCheckbox.checked;
                this.renderDiff();
            });
        }

        // Navigation buttons (both regular and floating)
        const jumpNextBtns = document.querySelectorAll('#jump-next-diff');
        const jumpPrevBtns = document.querySelectorAll('#jump-prev-diff');
        
        jumpNextBtns.forEach(btn => {
            btn.addEventListener('click', () => this.jumpToNextDiff());
        });
        
        jumpPrevBtns.forEach(btn => {
            btn.addEventListener('click', () => this.jumpToPreviousDiff());
        });

        // Floating navigation controls
        const minimizeBtn = document.getElementById('minimize-floating-nav');
        const minimizedNav = document.getElementById('minimized-floating-nav');
        const floatingNav = document.getElementById('floating-diff-nav');

        if (minimizeBtn && minimizedNav && floatingNav) {
            minimizeBtn.addEventListener('click', () => {
                floatingNav.style.display = 'none';
                minimizedNav.style.display = 'block';
            });

            minimizedNav.addEventListener('click', () => {
                minimizedNav.style.display = 'none';
                floatingNav.style.display = 'block';
            });
        }

        // Show/hide floating nav based on scroll and diff content
        this.setupFloatingNavigation();

        // Keyboard shortcuts (like new)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'n' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.jumpToNextDiff();
            } else if (e.key === 'p' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.jumpToPreviousDiff();
            }
        });
    }

    // Main diff rendering function (new inspired)
    renderDiff() {
        const contentA = document.getElementById('diff-content-a')?.textContent || '';
        const contentB = document.getElementById('diff-content-b')?.textContent || '';
        const resultContainer = document.getElementById('diff-result');

        if (!resultContainer) return;

        // Show loading state
        resultContainer.innerHTML = `
            <div class="text-center text-gray-500 py-8">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-500 mx-auto mb-2"></div>
                Processing differences...
            </div>
        `;

        // Use setTimeout to allow UI to update
        setTimeout(() => {
            this.computeAndDisplayDiff(contentA, contentB, resultContainer);
        }, 10);
    }

    // Compute and display differences based on selected type
    computeAndDisplayDiff(contentA, contentB, resultContainer) {
        let diff;
        // Configure options for better tab and whitespace handling
        const options = { 
            ignoreWhitespace: this.ignoreWhitespace,
            // Don't ignore tabs even when ignoring whitespace, as they're structural
            ignoreCase: false,
            // For tabular data, we want to preserve structure
            newlineIsToken: this.currentDiffType === 'diffLines'
        };

        // Calculate MD5 for change detection (like new)
        const md5A = this.calculateMD5(contentA);
        const md5B = this.calculateMD5(contentB);
        
        // If content is identical, show no changes message
        if (md5A === md5B) {
            resultContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    No differences detected
                </div>
            `;
            this.updateChangeCounter(0);
            return;
        }

        // Check if Diff library is available
        if (typeof Diff === 'undefined') {
            console.error('jsdiff library not loaded');
            resultContainer.innerHTML = `
                <div class="text-center text-red-500 py-8">
                    <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Error: Diff library not loaded. Please refresh the page.
                </div>
            `;
            return;
        }

        // Perform diff based on selected type (new style)
        try {
            switch(this.currentDiffType) {
                case 'diffWords':
                    // For words, use a custom approach that respects tabs
                    diff = this.customWordDiff(contentA, contentB, options);
                    break;
                case 'diffLines':
                    diff = Diff.diffLines(contentA, contentB, options);
                    break;
                case 'diffChars':
                    diff = Diff.diffChars(contentA, contentB, options);
                    break;
                case 'diffJson':
                    try {
                        const jsonA = JSON.parse(contentA || '{}');
                        const jsonB = JSON.parse(contentB || '{}');
                        diff = Diff.diffJson(jsonA, jsonB);
                    } catch (e) {
                        console.warn('Invalid JSON, falling back to word diff:', e);
                        // Fall back to words if not valid JSON
                        diff = this.customWordDiff(contentA, contentB, options);
                    }
                    break;
                default:
                    diff = this.customWordDiff(contentA, contentB, options);
            }

            this.renderDiffResult(diff, resultContainer);
        } catch (error) {
            console.error('Diff calculation error:', error);
            resultContainer.innerHTML = `
                <div class="text-center text-red-500 py-8">
                    <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Error calculating differences: ${error.message}
                </div>
            `;
        }
    }

    // Custom word diff that preserves tabs and handles tabular data better
    customWordDiff(contentA, contentB, options) {
        // If preserve tabs is enabled and we're ignoring whitespace
        if (this.preserveTabs && options.ignoreWhitespace) {
            // Custom implementation that ignores spaces but preserves tabs
            const customOptions = {
                ...options,
                ignoreWhitespace: false // Handle whitespace manually
            };
            
            // Pre-process content to normalize spaces but preserve tabs
            const normalizeContent = (content) => {
                if (!this.ignoreWhitespace) return content;
                // Replace multiple spaces with single space, but keep tabs
                return content.replace(/ +/g, ' ').replace(/^ +| +$/gm, '');
            };
            
            const normalizedA = normalizeContent(contentA);
            const normalizedB = normalizeContent(contentB);
            
            return Diff.diffWordsWithSpace(normalizedA, normalizedB, customOptions);
        } else if (!this.preserveTabs && options.ignoreWhitespace) {
            // Standard behavior - ignore all whitespace including tabs
            return Diff.diffWords(contentA, contentB, options);
        } else {
            // Standard word diff that treats all whitespace as significant
            return Diff.diffWordsWithSpace(contentA, contentB, options);
        }
    }

    // Render the diff result with proper HTML tags (new style)
    renderDiffResult(diff, container) {
        const fragment = document.createDocumentFragment();
        this.diffResults = [];
        this.changeCount = 0;

        // Create wrapper div with appropriate styling
        const wrapperDiv = document.createElement('div');
        wrapperDiv.className = `diff-display ${this.currentDiffType.replace('diff', '').toLowerCase()}-diff`;

        for (let i = 0; i < diff.length; i++) {
            // Handle swapped additions/deletions for better visual flow
            if (diff[i].added && diff[i + 1] && diff[i + 1].removed) {
                const swap = diff[i];
                diff[i] = diff[i + 1];
                diff[i + 1] = swap;
            }

            let element;
            
            if (diff[i].removed) {
                // Create <del> element for removed content
                element = document.createElement('del');
                element.className = 'diff-change diff-removed';
                element.setAttribute('title', 'Removed content');
                element.setAttribute('data-change-type', 'removed');
                
                // Add content with proper tab and whitespace preservation
                this.setElementContent(element, diff[i].value);
                
                this.diffResults.push(element);
                this.changeCount++;
                
            } else if (diff[i].added) {
                // Create <ins> element for added content
                element = document.createElement('ins');
                element.className = 'diff-change diff-added';
                element.setAttribute('title', 'Added content');
                element.setAttribute('data-change-type', 'added');
                
                // Add content with proper tab and whitespace preservation
                this.setElementContent(element, diff[i].value);
                
                this.diffResults.push(element);
                this.changeCount++;
                
            } else {
                // Unchanged content - preserve tabs and formatting
                element = this.createTextElementWithTabs(diff[i].value);
            }
            
            wrapperDiv.appendChild(element);
        }

        // Clear container and add new content
        container.innerHTML = '';
        container.appendChild(wrapperDiv);

        // Add IDs for navigation and update UI
        this.setupNavigation();
        this.updateChangeCounter(this.changeCount);
        this.currentDiffIndex = 0;

        // Update floating navigation
        if (this.showFloatingNavIfNeeded) {
            this.showFloatingNavIfNeeded();
        }

        // Auto-scroll to first change if any
        if (this.diffResults.length > 0) {
            setTimeout(() => this.jumpToChange(0), 100);
        }
    }

    // Helper method to set element content while preserving tabs
    setElementContent(element, content) {
        // Always preserve tabs when the preserveTabs option is enabled (default)
        if (this.preserveTabs && content.includes('\t')) {
            // Create span to hold the content with preserved tabs
            const span = document.createElement('span');
            span.style.whiteSpace = 'pre-wrap';
            span.style.tabSize = '4'; // Set tab width
            span.textContent = content;
            element.appendChild(span);
        } else if (!this.preserveTabs && content.includes('\t')) {
            // Convert tabs to spaces if preserve tabs is disabled
            const span = document.createElement('span');
            span.textContent = content.replace(/\t/g, '    '); // Convert tabs to 4 spaces
            element.appendChild(span);
        } else {
            // Regular content without tabs
            const span = document.createElement('span');
            span.textContent = content;
            element.appendChild(span);
        }
    }

    // Helper method to create text elements that preserve tabs
    createTextElementWithTabs(content) {
        if (this.preserveTabs && content.includes('\t')) {
            // Create a span element to preserve tab formatting
            const span = document.createElement('span');
            span.style.whiteSpace = 'pre-wrap';
            span.style.tabSize = '4'; // Set tab width to 4 spaces equivalent
            span.textContent = content;
            return span;
        } else if (!this.preserveTabs && content.includes('\t')) {
            // Convert tabs to spaces
            const span = document.createElement('span');
            span.textContent = content.replace(/\t/g, '    ');
            return span;
        } else {
            // Regular text node for content without tabs
            return document.createTextNode(content);
        }
    }

    // Setup navigation IDs and classes
    setupNavigation() {
        this.diffResults.forEach((element, index) => {
            element.id = `diff-change-${index}`;
            element.setAttribute('data-change-index', index);
        });
    }

    // Jump to next difference
    jumpToNextDiff() {
        if (this.diffResults.length === 0) return;
        this.currentDiffIndex = (this.currentDiffIndex + 1) % this.diffResults.length;
        this.jumpToChange(this.currentDiffIndex);
    }

    // Jump to previous difference  
    jumpToPreviousDiff() {
        if (this.diffResults.length === 0) return;
        this.currentDiffIndex = (this.currentDiffIndex - 1 + this.diffResults.length) % this.diffResults.length;
        this.jumpToChange(this.currentDiffIndex);
    }

    // Jump to specific change by index
    jumpToChange(index) {
        if (index < 0 || index >= this.diffResults.length) return;

        // Remove previous highlights
        document.querySelectorAll('.diff-highlight').forEach(el => {
            el.classList.remove('diff-highlight');
        });

        // Highlight current change
        const targetElement = this.diffResults[index];
        if (targetElement) {
            targetElement.classList.add('diff-highlight');
            
            // Smooth scroll to element (new style)
            targetElement.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center',
                inline: 'nearest'
            });

            this.currentDiffIndex = index;
            this.updateJumpCounter();
        }
    }

    // Update change counter display
    updateChangeCounter(count) {
        const counter = document.getElementById('diff-counter');
        if (counter) {
            if (count === 0) {
                counter.textContent = 'No changes';
                counter.className = 'text-sm text-gray-500';
            } else {
                counter.textContent = `${count} change${count !== 1 ? 's' : ''}`;
                counter.className = 'text-sm text-blue-600 font-medium';
            }
        }
    }

    // Update jump navigation counter
    updateJumpCounter() {
        const jumpCounter = document.getElementById('jump-counter');
        const floatingJumpCounter = document.getElementById('floating-jump-counter');
        
        if (this.diffResults.length > 0) {
            const counterText = `${this.currentDiffIndex + 1} of ${this.diffResults.length}`;
            if (jumpCounter) jumpCounter.textContent = counterText;
            if (floatingJumpCounter) floatingJumpCounter.textContent = counterText;
        } else {
            if (jumpCounter) jumpCounter.textContent = '-';
            if (floatingJumpCounter) floatingJumpCounter.textContent = '-';
        }
    }

    // Setup floating navigation behavior
    setupFloatingNavigation() {
        const floatingNav = document.getElementById('floating-diff-nav');
        const diffResult = document.getElementById('diff-result');
        
        if (!floatingNav || !diffResult) return;

        // Show floating nav when diff content is present and user scrolls
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (this.diffResults.length > 0) {
                    if (entry.isIntersecting) {
                        // Diff content is visible, hide floating nav
                        floatingNav.style.display = 'none';
                    } else {
                        // Diff content is not fully visible, show floating nav
                        floatingNav.style.display = 'block';
                    }
                }
            });
        }, {
            threshold: 0.3 // Show floating nav when less than 30% of diff content is visible
        });

        observer.observe(diffResult);

        // Also show floating nav when there are changes to navigate
        this.showFloatingNavIfNeeded = () => {
            if (this.diffResults.length > 1) {
                // Only show if diff content is not fully visible
                const rect = diffResult.getBoundingClientRect();
                const isFullyVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
                
                if (!isFullyVisible) {
                    floatingNav.style.display = 'block';
                }
            } else {
                floatingNav.style.display = 'none';
            }
        };
    }

    // Calculate MD5 hash for change detection (like new)
    calculateMD5(content) {
        // Simple hash function for basic change detection
        // In production, you might want to use a proper MD5 library
        let hash = 0;
        if (content.length === 0) return hash.toString();
        
        for (let i = 0; i < content.length; i++) {
            const char = content.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return hash.toString();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if diff elements are present
    if (!document.getElementById('diff-result')) {
        console.log('No diff result container found, skipping diff renderer initialization');
        return;
    }

    // Check if jsdiff library is loaded
    if (typeof Diff === 'undefined') {
        console.error('jsdiff library not loaded, trying to load it');
        // Try to load the library if it's not available
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/diff@5.1.0/dist/diff.min.js';
        script.onload = function() {
            console.log('jsdiff library loaded, initializing diff renderer');
            window.diffRenderer = new DiffRenderer();
            window.diffRenderer.init();
        };
        script.onerror = function() {
            console.error('Failed to load jsdiff library');
            const resultContainer = document.getElementById('diff-result');
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div class="text-center text-red-500 py-8">
                        <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        Failed to load diff library. Please refresh the page.
                    </div>
                `;
            }
        };
        document.head.appendChild(script);
    } else {
        console.log('jsdiff library available, initializing diff renderer');
        window.diffRenderer = new DiffRenderer();
        window.diffRenderer.init();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DiffRenderer;
}