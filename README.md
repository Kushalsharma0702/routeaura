# RouteAura 🌍✈️

A modern travel and tour management system built with React and TypeScript. This web application allows users to browse travel packages, manage bookings, and provides administrators with powerful tools to manage destinations, routes, and user bookings.

## 📚 Project Information

**Course:** Web Technologies  
**Institution:** IILM University  
**Submitted to:** Mr. Shobhit Agarwal  

**Team Members:**
- Kushal
- Shikha Singh
- Kunwar Aryan Singh
- Ruprekha

---

## ✨ Features

### For Clients
- **Browse Packages:** Explore various travel packages with detailed information
- **Book Tours:** Easy booking process for selected packages
- **My Bookings:** View and manage all your bookings in one place
- **Profile Management:** Update personal information and preferences
- **Interactive Dashboard:** Get insights into your travel history and upcoming trips

### For Administrators
- **User Management:** Manage all registered users
- **Package Management:** Create, update, and delete travel packages
- **Destination Management:** Add and manage travel destinations
- **Route Management:** Configure and optimize travel routes
- **Booking Management:** Oversee all bookings with complete details
- **Analytics Dashboard:** View statistics and insights about the platform

---

## 🛠️ Tech Stack

- **Frontend Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **UI Components:** Shadcn/ui with Radix UI primitives
- **Styling:** Tailwind CSS
- **State Management:** React Context API
- **Form Handling:** React Hook Form with Zod validation
- **Routing:** React Router DOM
- **Data Fetching:** TanStack Query (React Query)
- **Animations:** Framer Motion
- **Icons:** Lucide React
- **Testing:** Vitest
- **Package Manager:** Bun

---

## 📦 Installation

### Prerequisites
Make sure you have the following installed:
- Node.js (v18 or higher)
- Bun (or npm/yarn/pnpm)

### Steps to Run Locally

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd escapade-central-main
   ```

2. **Install dependencies**
   ```bash
   bun install
   ```
   
   Or if you're using npm:
   ```bash
   npm install
   ```

3. **Start the development server**
   ```bash
   bun run dev
   ```
   
   Or with npm:
   ```bash
   npm run dev
   ```

4. **Open your browser**
   Navigate to `http://localhost:5173` (or the port shown in your terminal)

---

## 🚀 Available Scripts

- `bun run dev` - Start development server
- `bun run build` - Build for production
- `bun run preview` - Preview production build
- `bun run lint` - Run ESLint
- `bun run test` - Run tests once
- `bun run test:watch` - Run tests in watch mode

---

## 📁 Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── layouts/     # Layout components
│   └── ui/          # Shadcn UI components
├── contexts/        # React Context providers
├── data/            # Mock data and constants
├── hooks/           # Custom React hooks
├── lib/             # Utility functions
├── pages/           # Page components
│   ├── admin/       # Admin dashboard pages
│   └── client/      # Client-facing pages
└── test/            # Test files and setup
```

---

## 🎨 Key Components

### Client Side
- **Dashboard:** Overview of bookings and recommendations
- **Browse Packages:** Grid view of available travel packages
- **My Bookings:** List of all user bookings with status
- **Profile:** User profile management

### Admin Side
- **Admin Dashboard:** Statistics and overview
- **Manage Users:** User administration panel
- **Manage Packages:** CRUD operations for packages
- **Manage Destinations:** Destination management
- **Manage Routes:** Route configuration
- **Manage Bookings:** Booking oversight and updates

---

## 🔐 Authentication

The application includes a basic authentication system with different access levels:
- **Client Users:** Can browse packages and manage their bookings
- **Admin Users:** Have full access to management features

---

## 🎯 Future Enhancements

- [ ] Payment gateway integration
- [ ] Real-time booking notifications
- [ ] Advanced search and filtering
- [ ] Multi-language support
- [ ] Mobile application
- [ ] Review and rating system
- [ ] Email notifications
- [ ] Export reports to PDF

---

## 🤝 Contributing

This is an academic project developed for the Web Technologies course at IILM University. If you'd like to suggest improvements:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add some improvement'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Open a Pull Request

---

## 📝 License

This project is created for educational purposes as part of the Web Technologies course at IILM University.

---

## 🙏 Acknowledgments

- Thanks to **Mr. Shobhit Agarwal** for guidance throughout the project
- IILM University for providing the platform to learn and build
- The open-source community for amazing tools and libraries

---

## 📞 Contact

For any queries regarding this project, please reach out to any of the team members mentioned above.

---

**Made with ❤️ by Team Aurocode**
