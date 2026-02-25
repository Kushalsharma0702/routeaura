/**
 * Mock Data for Escapade Central
 * 
 * This file contains all the sample data used in the application for demonstration
 * In a production app, this would be replaced with API calls to a backend server
 * 
 * Includes:
 * - User accounts (admin & clients)
 * - Travel packages
 * - Destinations
 * - Routes
 * - Bookings
 * - Analytics data
 */

// ==================== TYPE DEFINITIONS ====================

/**
 * User Account Structure
 * Represents both admin and client users in the system
 */
export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'client';  // Determines access level
  phone?: string;
  avatar?: string;
  joinedDate: string;
}

/**
 * Travel Package Structure
 * Contains all details about a tour package
 */
export interface TravelPackage {
  id: string;
  title: string;
  destination: string;
  description: string;
  price: number;  // In Indian Rupees
  duration: number;  // In days
  availableSeats: number;
  travelDate: string;
  images: string[];  // Array of image URLs
  rating: number;  // Out of 5
  category: string;  // Beach, Adventure, Cultural, etc.
  tags: string[];  // For filtering and search
  visible: boolean;  // Controls if package is shown to users
}

/**
 * Booking Structure
 * Represents a customer's booking for a travel package
 */
export interface Booking {
  id: string;
  packageId: string;
  packageName: string;
  clientId: string;
  clientName: string;
  clientEmail: string;
  clientPhone: string;
  travelers: number;  // Number of people in the group
  travelDate: string;
  status: 'pending' | 'approved' | 'rejected';
  paymentStatus: 'paid' | 'unpaid' | 'refunded';
  totalAmount: number;
  bookedDate: string;
}

/**
 * Destination Structure
 * Information about travel destinations
 */
export interface Destination {
  id: string;
  name: string;
  country: string;
  description: string;
  images: string[];
  travelSeason: string;  // Best time to visit
  attractions: string[];  // Popular places to visit
}

/**
 * Route Structure
 * Travel routes between locations
 */
export interface Route {
  id: string;
  source: string;
  destination: string;
  stops: string[];  // Intermediate stops
  distance: string;
  travelMode: 'Flight' | 'Road' | 'Train';
  duration: string;
}

// ==================== DEMO DATA ====================

/**
 * Demo User Accounts
 * Includes 1 admin and 4 client users for testing
 */
export const demoUsers: User[] = [
  { id: '1', name: 'Admin User', email: 'admin@routeaura.com', role: 'admin', phone: '+91 98100 10001', joinedDate: '2024-01-15' },
  { id: '2', name: 'Priya Sharma', email: 'client@routeaura.com', role: 'client', phone: '+91 98200 20001', joinedDate: '2024-03-20' },
  { id: '3', name: 'Rahul Verma', email: 'rahul@example.com', role: 'client', phone: '+91 99100 30002', joinedDate: '2024-05-10' },
  { id: '4', name: 'Ananya Iyer', email: 'ananya@example.com', role: 'client', phone: '+91 98765 40003', joinedDate: '2024-06-01' },
  { id: '5', name: 'Vikram Singh', email: 'vikram@example.com', role: 'client', phone: '+91 97654 50004', joinedDate: '2024-07-15' },
];

/**
 * Travel Packages
 * 6 carefully curated tour packages covering different regions of India
 * Each package includes details about destination, pricing, dates, and images
 */
export const travelPackages: TravelPackage[] = [
  {
    id: 'pkg-1', title: 'Goa Beach Bliss', destination: 'Goa',
    description: 'Soak in the sun on pristine Goan beaches, explore Portuguese-era churches, enjoy vibrant nightlife, and savour fresh seafood by the shore.',
    price: 18999, duration: 5, availableSeats: 25, travelDate: '2026-04-15',
    images: [
      'https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=800',
      'https://images.unsplash.com/photo-1587922546307-776227941871?w=800',
      'https://images.unsplash.com/photo-1614082242765-7c98ca0f3df3?w=800',
    ],
    rating: 4.8, category: 'Beach', tags: ['Family', 'Relaxation', 'Nightlife'], visible: true,
  },
  {
    id: 'pkg-2', title: 'Manali & Rohtang Adventure', destination: 'Manali, Himachal Pradesh',
    description: 'Trek through snow-capped peaks, cross the legendary Rohtang Pass, and camp under the Himalayan stars. A true adventure experience.',
    price: 24999, duration: 7, availableSeats: 15, travelDate: '2026-05-01',
    images: [
      'https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=800',
      'https://images.unsplash.com/photo-1585409677983-0f6c41ca9c3b?w=800',
      'https://images.unsplash.com/photo-1544735716-392fe2489ffa?w=800',
    ],
    rating: 4.9, category: 'Adventure', tags: ['Adventure', 'Trekking', 'Nature'], visible: true,
  },
  {
    id: 'pkg-3', title: 'Rajasthan Royal Heritage', destination: 'Jaipur & Udaipur, Rajasthan',
    description: 'Walk through majestic forts, cruise Lake Pichola, and experience royal Rajasthani hospitality with traditional folk performances.',
    price: 32999, duration: 8, availableSeats: 20, travelDate: '2026-03-20',
    images: [
      'https://images.unsplash.com/photo-1599661046289-e31897846e41?w=800',
      'https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=800',
      'https://images.unsplash.com/photo-1477587458883-47145ed94245?w=800',
    ],
    rating: 4.7, category: 'Cultural', tags: ['Culture', 'Heritage', 'History'], visible: true,
  },
  {
    id: 'pkg-4', title: 'Kerala Backwaters Luxury', destination: 'Alleppey & Munnar, Kerala',
    description: 'Cruise on a luxury houseboat through Kerala\'s serene backwaters, visit spice plantations in Munnar, and indulge in Ayurvedic spa treatments.',
    price: 45999, duration: 6, availableSeats: 10, travelDate: '2026-06-10',
    images: [
      'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800',
      'https://images.unsplash.com/photo-1609920658906-8223bd289001?w=800',
      'https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=800',
    ],
    rating: 5.0, category: 'Luxury', tags: ['Luxury', 'Wellness', 'Honeymoon'], visible: true,
  },
  {
    id: 'pkg-5', title: 'Leh-Ladakh Expedition', destination: 'Leh, Ladakh',
    description: 'Ride through the highest motorable roads, visit ancient monasteries, and witness Pangong Lake\'s magical colour changes.',
    price: 29999, duration: 9, availableSeats: 12, travelDate: '2026-07-05',
    images: [
      'https://images.unsplash.com/photo-1626015365107-39ce44d3c17c?w=800',
      'https://images.unsplash.com/photo-1589793907316-f94025b46850?w=800',
      'https://images.unsplash.com/photo-1573053986637-a01ec5394bfa?w=800',
    ],
    rating: 4.6, category: 'Adventure', tags: ['Adventure', 'Biking', 'Nature'], visible: true,
  },
  {
    id: 'pkg-6', title: 'Andaman Island Escape', destination: 'Port Blair & Havelock, Andaman',
    description: 'Dive into crystal-clear waters, explore coral reefs, visit the historic Cellular Jail, and relax on white-sand beaches.',
    price: 35999, duration: 6, availableSeats: 18, travelDate: '2026-05-20',
    images: [
      'https://images.unsplash.com/photo-1544550581-5f7ceaf7f992?w=800',
      'https://images.unsplash.com/photo-1559128010-7c1ad6e1b6a5?w=800',
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800',
    ],
    rating: 4.8, category: 'Beach', tags: ['Beach', 'Scuba Diving', 'Romantic'], visible: true,
  },
];

/**
 * Popular Travel Destinations
 * Featured destinations with detailed information
 * Used in the destination management section
 */
export const destinations: Destination[] = [
  {
    id: 'dest-1', name: 'Goa', country: 'India',
    description: 'India\'s party capital with stunning beaches, Portuguese heritage, water sports, and a buzzing nightlife scene.',
    images: ['https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=800', 'https://images.unsplash.com/photo-1587922546307-776227941871?w=800'],
    travelSeason: 'Oct - Mar', attractions: ['Baga Beach', 'Basilica of Bom Jesus', 'Dudhsagar Falls', 'Fort Aguada'],
  },
  {
    id: 'dest-2', name: 'Manali', country: 'India',
    description: 'A Himalayan hill station with snow-capped peaks, adventure sports, and lush green valleys.',
    images: ['https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=800', 'https://images.unsplash.com/photo-1585409677983-0f6c41ca9c3b?w=800'],
    travelSeason: 'Oct - Jun', attractions: ['Rohtang Pass', 'Solang Valley', 'Hadimba Temple', 'Old Manali'],
  },
  {
    id: 'dest-3', name: 'Jaipur', country: 'India',
    description: 'The Pink City — a vibrant blend of majestic forts, colourful bazaars, and royal Rajasthani culture.',
    images: ['https://images.unsplash.com/photo-1599661046289-e31897846e41?w=800', 'https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=800'],
    travelSeason: 'Oct - Mar', attractions: ['Hawa Mahal', 'Amber Fort', 'City Palace', 'Jantar Mantar'],
  },
  {
    id: 'dest-4', name: 'Kerala', country: 'India',
    description: 'God\'s Own Country — serene backwaters, lush tea gardens, Ayurveda, and tropical beaches.',
    images: ['https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800', 'https://images.unsplash.com/photo-1609920658906-8223bd289001?w=800'],
    travelSeason: 'Sep - Mar', attractions: ['Alleppey Backwaters', 'Munnar Tea Gardens', 'Periyar Wildlife', 'Kovalam Beach'],
  },
  {
    id: 'dest-5', name: 'Ladakh', country: 'India',
    description: 'Land of high passes — stark mountains, ancient monasteries, and turquoise Pangong Lake.',
    images: ['https://images.unsplash.com/photo-1626015365107-39ce44d3c17c?w=800', 'https://images.unsplash.com/photo-1589793907316-f94025b46850?w=800'],
    travelSeason: 'Jun - Sep', attractions: ['Pangong Lake', 'Nubra Valley', 'Thiksey Monastery', 'Khardung La'],
  },
];

/**
 * Travel Routes
 * Predefined routes between major cities
 * Includes distance, duration, and mode of transport
 */
export const routes: Route[] = [
  { id: 'rt-1', source: 'Delhi', destination: 'Manali', stops: ['Chandigarh', 'Mandi'], distance: '540 km', travelMode: 'Road', duration: '12h' },
  { id: 'rt-2', source: 'Mumbai', destination: 'Goa', stops: [], distance: '590 km', travelMode: 'Road', duration: '10h' },
  { id: 'rt-3', source: 'Delhi', destination: 'Jaipur', stops: [], distance: '280 km', travelMode: 'Train', duration: '4.5h' },
  { id: 'rt-4', source: 'Chennai', destination: 'Alleppey', stops: ['Kochi'], distance: '700 km', travelMode: 'Train', duration: '12h' },
  { id: 'rt-5', source: 'Delhi', destination: 'Leh', stops: ['Srinagar', 'Kargil'], distance: '1,025 km', travelMode: 'Road', duration: '2 days' },
  { id: 'rt-6', source: 'Kolkata', destination: 'Port Blair', stops: [], distance: '1,300 km', travelMode: 'Flight', duration: '2.5h' },
];

/**
 * Bookings Data
 * Sample bookings from different users with various statuses
 * Demonstrates approved, pending, and rejected booking scenarios
 */
export const bookings: Booking[] = [
  {
    id: 'bk-1', packageId: 'pkg-1', packageName: 'Goa Beach Bliss', clientId: '2',
    clientName: 'Priya Sharma', clientEmail: 'client@routeaura.com', clientPhone: '+91 98200 20001',
    travelers: 2, travelDate: '2026-04-15', status: 'approved', paymentStatus: 'paid',
    totalAmount: 37998, bookedDate: '2026-01-10',
  },
  {
    id: 'bk-2', packageId: 'pkg-3', packageName: 'Rajasthan Royal Heritage', clientId: '3',
    clientName: 'Rahul Verma', clientEmail: 'rahul@example.com', clientPhone: '+91 99100 30002',
    travelers: 1, travelDate: '2026-03-20', status: 'pending', paymentStatus: 'unpaid',
    totalAmount: 32999, bookedDate: '2026-02-01',
  },
  {
    id: 'bk-3', packageId: 'pkg-4', packageName: 'Kerala Backwaters Luxury', clientId: '2',
    clientName: 'Priya Sharma', clientEmail: 'client@routeaura.com', clientPhone: '+91 98200 20001',
    travelers: 2, travelDate: '2026-06-10', status: 'pending', paymentStatus: 'unpaid',
    totalAmount: 91998, bookedDate: '2026-02-15',
  },
  {
    id: 'bk-4', packageId: 'pkg-2', packageName: 'Manali & Rohtang Adventure', clientId: '4',
    clientName: 'Ananya Iyer', clientEmail: 'ananya@example.com', clientPhone: '+91 98765 40003',
    travelers: 3, travelDate: '2026-05-01', status: 'approved', paymentStatus: 'paid',
    totalAmount: 74997, bookedDate: '2026-01-20',
  },
  {
    id: 'bk-5', packageId: 'pkg-5', packageName: 'Leh-Ladakh Expedition', clientId: '5',
    clientName: 'Vikram Singh', clientEmail: 'vikram@example.com', clientPhone: '+91 97654 50004',
    travelers: 2, travelDate: '2026-07-05', status: 'rejected', paymentStatus: 'refunded',
    totalAmount: 59998, bookedDate: '2026-02-05',
  },
];

/**
 * Monthly Bookings Analytics
 * Used for the line chart in admin dashboard
 * Shows booking trends throughout the year
 */
export const monthlyBookingsData = [
  { month: 'Jan', bookings: 12 }, { month: 'Feb', bookings: 19 },
  { month: 'Mar', bookings: 15 }, { month: 'Apr', bookings: 25 },
  { month: 'May', bookings: 22 }, { month: 'Jun', bookings: 30 },
  { month: 'Jul', bookings: 28 }, { month: 'Aug', bookings: 35 },
  { month: 'Sep', bookings: 20 }, { month: 'Oct', bookings: 18 },
  { month: 'Nov', bookings: 24 }, { month: 'Dec', bookings: 32 },
];

/**
 * Destination Popularity Data
 * Used for the pie chart in admin dashboard
 * Shows distribution of bookings by package category
 */
export const destinationData = [
  { name: 'Beach', value: 40, fill: 'hsl(239 84% 67%)' },
  { name: 'Adventure', value: 25, fill: 'hsl(187 92% 53%)' },
  { name: 'Cultural', value: 20, fill: 'hsl(152 60% 42%)' },
  { name: 'Luxury', value: 15, fill: 'hsl(38 92% 50%)' },
];

// ==================== UTILITY FUNCTIONS ====================

/**
 * Currency Formatter
 * Formats numbers into Indian Rupee format with proper separators
 * Example: 25000 → ₹25,000
 */
export const formatINR = (amount: number) =>
  `₹${amount.toLocaleString('en-IN')}`;
