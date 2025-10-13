// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const toggleButton = document.getElementById('sidebar-toggle');

    if (toggleButton && sidebar && mainContent) {
        toggleButton.addEventListener('click', function() {
            // Toggle the custom CSS class we defined in input.css
            sidebar.classList.toggle('sidebar-closed');

            // Optionally, adjust the margin/width of the main content area 
            // We use transition-all on main-content to handle the push/pull effect.
            // Tailwind's flex-grow handles the content area automatically.
        });
    }
});