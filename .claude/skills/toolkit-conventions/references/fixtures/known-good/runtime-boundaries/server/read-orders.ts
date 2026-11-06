import "server-only";
import { db } from "./db";
export const readOrders = () => db.query();
